#include <ntddk.h>
#include <wdf.h>
#include <wdfsec.h>
#include <ntstrsafe.h>
#include <hidport.h>
#include <vhf.h>

#include "NativeInputsVhfIoctl.h"

#define NI_VHF_VENDOR_ID  0xFFFF /* Reserved/test-style ID; this is not a physical USB VID. */
#define NI_VHF_PRODUCT_ID 0x4E49
#define NI_VHF_VERSION    0x0100

typedef struct _DEVICE_CONTEXT {
    VHFHANDLE KeyboardHandle;
    VHFHANDLE MouseHandle;
} DEVICE_CONTEXT, *PDEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DEVICE_CONTEXT, DeviceGetContext)

static const UCHAR KeyboardReportDescriptor[] = {
    0x05, 0x01,       /* USAGE_PAGE (Generic Desktop) */
    0x09, 0x06,       /* USAGE (Keyboard) */
    0xA1, 0x01,       /* COLLECTION (Application) */
    0x85, 0x01,       /*   REPORT_ID (1) */
    0x05, 0x07,       /*   USAGE_PAGE (Keyboard/Keypad) */
    0x19, 0xE0,       /*   USAGE_MINIMUM (Keyboard LeftControl) */
    0x29, 0xE7,       /*   USAGE_MAXIMUM (Keyboard Right GUI) */
    0x15, 0x00,       /*   LOGICAL_MINIMUM (0) */
    0x25, 0x01,       /*   LOGICAL_MAXIMUM (1) */
    0x75, 0x01,       /*   REPORT_SIZE (1) */
    0x95, 0x08,       /*   REPORT_COUNT (8) */
    0x81, 0x02,       /*   INPUT (Data,Var,Abs) modifier bits */
    0x95, 0x01,       /*   REPORT_COUNT (1) */
    0x75, 0x08,       /*   REPORT_SIZE (8) */
    0x81, 0x01,       /*   INPUT (Const,Array,Abs) reserved byte */
    0x95, 0x06,       /*   REPORT_COUNT (6) */
    0x75, 0x08,       /*   REPORT_SIZE (8) */
    0x15, 0x00,       /*   LOGICAL_MINIMUM (0) */
    0x25, 0x73,       /*   LOGICAL_MAXIMUM (115) */
    0x05, 0x07,       /*   USAGE_PAGE (Keyboard/Keypad) */
    0x19, 0x00,       /*   USAGE_MINIMUM (Reserved) */
    0x29, 0x73,       /*   USAGE_MAXIMUM (F24) */
    0x81, 0x00,       /*   INPUT (Data,Array,Abs) */
    0xC0              /* END_COLLECTION */
};

static WCHAR KeyboardInstanceId[] = L"NativeInputsKeyboard";
static WCHAR MouseInstanceId[] = L"NativeInputsMouse";

static const UCHAR MouseReportDescriptor[] = {
    0x05, 0x01,       /* USAGE_PAGE (Generic Desktop) */
    0x09, 0x02,       /* USAGE (Mouse) */
    0xA1, 0x01,       /* COLLECTION (Application) */
    0x85, 0x02,       /*   REPORT_ID (2) */
    0x09, 0x01,       /*   USAGE (Pointer) */
    0xA1, 0x00,       /*   COLLECTION (Physical) */
    0x05, 0x09,       /*     USAGE_PAGE (Button) */
    0x19, 0x01,       /*     USAGE_MINIMUM (Button 1) */
    0x29, 0x05,       /*     USAGE_MAXIMUM (Button 5) */
    0x15, 0x00,       /*     LOGICAL_MINIMUM (0) */
    0x25, 0x01,       /*     LOGICAL_MAXIMUM (1) */
    0x95, 0x05,       /*     REPORT_COUNT (5) */
    0x75, 0x01,       /*     REPORT_SIZE (1) */
    0x81, 0x02,       /*     INPUT (Data,Var,Abs) buttons */
    0x95, 0x01,       /*     REPORT_COUNT (1) */
    0x75, 0x03,       /*     REPORT_SIZE (3) */
    0x81, 0x03,       /*     INPUT (Const,Var,Abs) padding */
    0x05, 0x01,       /*     USAGE_PAGE (Generic Desktop) */
    0x09, 0x30,       /*     USAGE (X) */
    0x09, 0x31,       /*     USAGE (Y) */
    0x09, 0x38,       /*     USAGE (Wheel) */
    0x15, 0x81,       /*     LOGICAL_MINIMUM (-127) */
    0x25, 0x7F,       /*     LOGICAL_MAXIMUM (127) */
    0x75, 0x08,       /*     REPORT_SIZE (8) */
    0x95, 0x03,       /*     REPORT_COUNT (3) */
    0x81, 0x06,       /*     INPUT (Data,Var,Rel) X/Y/Wheel */
    0xC0,             /*   END_COLLECTION */
    0xC0              /* END_COLLECTION */
};

static VOID
EvtFileCleanup(_In_ WDFFILEOBJECT FileObject)
{
    WDFDEVICE device = WdfFileObjectGetDevice(FileObject);
    PDEVICE_CONTEXT context = DeviceGetContext(device);
    UCHAR emptyKeyboard[NI_KEYBOARD_REPORT_LENGTH] = { 0 };
    UCHAR emptyMouse[NI_MOUSE_REPORT_LENGTH] = { 0 };
    HID_XFER_PACKET packet;

    /* A closing/crashed client must not leave keys or mouse buttons held. */
    RtlZeroMemory(&packet, sizeof(packet));
    if (context->KeyboardHandle != NULL) {
        packet.reportBuffer = emptyKeyboard;
        packet.reportBufferLen = sizeof(emptyKeyboard);
        packet.reportId = NI_KEYBOARD_REPORT_ID;
        (VOID)VhfReadReportSubmit(context->KeyboardHandle, &packet);
    }
    if (context->MouseHandle != NULL) {
        RtlZeroMemory(&packet, sizeof(packet));
        packet.reportBuffer = emptyMouse;
        packet.reportBufferLen = sizeof(emptyMouse);
        packet.reportId = NI_MOUSE_REPORT_ID;
        (VOID)VhfReadReportSubmit(context->MouseHandle, &packet);
    }
}

static VOID
EvtDeviceContextCleanup(_In_ WDFOBJECT DeviceObject)
{
    PDEVICE_CONTEXT context = DeviceGetContext((WDFDEVICE)DeviceObject);
    PAGED_CODE();

    /* Stop submitting reports before synchronously deleting VHF children. */
    if (context->MouseHandle != NULL) {
        VhfDelete(context->MouseHandle, TRUE);
        context->MouseHandle = NULL;
    }
    if (context->KeyboardHandle != NULL) {
        VhfDelete(context->KeyboardHandle, TRUE);
        context->KeyboardHandle = NULL;
    }
}

static NTSTATUS
CreateVhfDevice(
    _In_ WDFDEVICE Device,
    _In_reads_bytes_(DescriptorLength) const UCHAR* Descriptor,
    _In_ USHORT DescriptorLength,
    _In_reads_bytes_(InstanceIdLength) PWSTR InstanceId,
    _In_ USHORT InstanceIdLength,
    _Out_ VHFHANDLE* Handle
)
{
    VHF_CONFIG config;
    NTSTATUS status;

    VHF_CONFIG_INIT(
        &config,
        WdfDeviceWdmGetDeviceObject(Device),
        DescriptorLength,
        (PUCHAR)Descriptor
    );
    config.VendorID = NI_VHF_VENDOR_ID;
    config.ProductID = NI_VHF_PRODUCT_ID;
    config.VersionNumber = NI_VHF_VERSION;
    config.InstanceID = InstanceId;
    config.InstanceIDLength = InstanceIdLength;

    status = VhfCreate(&config, Handle);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    status = VhfStart(*Handle);
    if (!NT_SUCCESS(status)) {
        VhfDelete(*Handle, TRUE);
        *Handle = NULL;
    }
    return status;
}

static VOID
EvtIoDeviceControl(
    _In_ WDFQUEUE Queue,
    _In_ WDFREQUEST Request,
    _In_ size_t OutputBufferLength,
    _In_ size_t InputBufferLength,
    _In_ ULONG IoControlCode
)
{
    WDFDEVICE device = WdfIoQueueGetDevice(Queue);
    PDEVICE_CONTEXT context = DeviceGetContext(device);
    PVOID inputBuffer = NULL;
    HID_XFER_PACKET packet;
    VHFHANDLE handle = NULL;
    UCHAR reportId = 0;
    size_t expectedLength = 0;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(OutputBufferLength);

    switch (IoControlCode) {
    case NI_IOCTL_SEND_KEYBOARD_REPORT:
        handle = context->KeyboardHandle;
        reportId = NI_KEYBOARD_REPORT_ID;
        expectedLength = NI_KEYBOARD_REPORT_LENGTH;
        break;
    case NI_IOCTL_SEND_MOUSE_REPORT:
        handle = context->MouseHandle;
        reportId = NI_MOUSE_REPORT_ID;
        expectedLength = NI_MOUSE_REPORT_LENGTH;
        break;
    default:
        WdfRequestComplete(Request, STATUS_INVALID_DEVICE_REQUEST);
        return;
    }

    if (InputBufferLength != expectedLength || handle == NULL) {
        WdfRequestComplete(Request, STATUS_INVALID_PARAMETER);
        return;
    }

    status = WdfRequestRetrieveInputBuffer(
        Request,
        expectedLength,
        &inputBuffer,
        NULL
    );
    if (!NT_SUCCESS(status)) {
        WdfRequestComplete(Request, status);
        return;
    }

    RtlZeroMemory(&packet, sizeof(packet));
    packet.reportBuffer = (PUCHAR)inputBuffer;
    packet.reportBufferLen = (ULONG)expectedLength;
    packet.reportId = reportId;

    /* VHF's default buffering policy copies/owns the report after this call. */
    status = VhfReadReportSubmit(handle, &packet);
    WdfRequestComplete(Request, status);
}

static NTSTATUS
EvtDeviceAdd(_In_ WDFDRIVER Driver, _Inout_ PWDFDEVICE_INIT DeviceInit)
{
    NTSTATUS status;
    WDFDEVICE device;
    WDF_OBJECT_ATTRIBUTES deviceAttributes;
    WDF_IO_QUEUE_CONFIG queueConfig;
    WDF_FILEOBJECT_CONFIG fileConfig;
    WDFQUEUE queue;
    DECLARE_CONST_UNICODE_STRING(symbolicLink, L"\\DosDevices\\NativeInputsVhf");
    DECLARE_CONST_UNICODE_STRING(deviceSddl, L"D:P(A;;GA;;;SY)(A;;GA;;;BA)");
    PDEVICE_CONTEXT context;

    UNREFERENCED_PARAMETER(Driver);
    PAGED_CODE();

    status = WdfDeviceInitAssignSDDLString(DeviceInit, &deviceSddl);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    WdfDeviceInitSetDeviceType(DeviceInit, FILE_DEVICE_UNKNOWN);
    WdfDeviceInitSetCharacteristics(DeviceInit, FILE_DEVICE_SECURE_OPEN, FALSE);
    WdfDeviceInitSetExclusive(DeviceInit, TRUE);
    WDF_FILEOBJECT_CONFIG_INIT(
        &fileConfig,
        WDF_NO_EVENT_CALLBACK,
        WDF_NO_EVENT_CALLBACK,
        EvtFileCleanup
    );
    WdfDeviceInitSetFileObjectConfig(DeviceInit, &fileConfig, WDF_NO_OBJECT_ATTRIBUTES);

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&deviceAttributes, DEVICE_CONTEXT);
    deviceAttributes.EvtCleanupCallback = EvtDeviceContextCleanup;

    status = WdfDeviceCreate(&DeviceInit, &deviceAttributes, &device);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    context = DeviceGetContext(device);
    context->KeyboardHandle = NULL;
    context->MouseHandle = NULL;

    status = WdfDeviceCreateSymbolicLink(device, &symbolicLink);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queueConfig, WdfIoQueueDispatchSequential);
    queueConfig.EvtIoDeviceControl = EvtIoDeviceControl;
    status = WdfIoQueueCreate(device, &queueConfig, WDF_NO_OBJECT_ATTRIBUTES, &queue);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    status = CreateVhfDevice(
        device,
        KeyboardReportDescriptor,
        (USHORT)sizeof(KeyboardReportDescriptor),
        KeyboardInstanceId,
        (USHORT)sizeof(KeyboardInstanceId),
        &context->KeyboardHandle
    );
    if (!NT_SUCCESS(status)) {
        return status;
    }

    status = CreateVhfDevice(
        device,
        MouseReportDescriptor,
        (USHORT)sizeof(MouseReportDescriptor),
        MouseInstanceId,
        (USHORT)sizeof(MouseInstanceId),
        &context->MouseHandle
    );
    return status;
}

NTSTATUS
DriverEntry(_In_ PDRIVER_OBJECT DriverObject, _In_ PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG config;
    WDF_DRIVER_CONFIG_INIT(&config, EvtDeviceAdd);
    return WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE
    );
}
