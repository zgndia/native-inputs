# Windows Virtual HID backend (VHF)

This companion driver exposes one **virtual** HID keyboard and one **virtual** HID mouse using Microsoft's Virtual HID Framework (VHF). It does not create a physical USB device and does not make software-generated input indistinguishable from hardware-originated input.

The Python backend sends standard HID report payloads to a small KMDF source driver. VHF then enumerates the keyboard and mouse collections through the Windows HID stack. Microsoft documents VHF as a kernel-mode HID source-driver framework; this project links against the WDK's `VhfKm.lib` and calls `VhfReadReportSubmit`.

## Current capabilities

- Keyboard key down/up reports, including modifiers and up to six simultaneous non-modifier keys (6-key rollover).
- Relative mouse movement, five mouse buttons, and vertical wheel scrolling.
- The existing `InputController` API is retained: `InputController("windows_vhf")`.

Not supported by this initial descriptor: Unicode text entry (`keyboard.type`), absolute pointer movement (`mouse.move_to`), horizontal wheel scrolling, and media/browser consumer keys. Use `keyboard.tap`/`press` for key usages and `mouse.move_relative` for pointer movement. Text entry is a distinct operation from physical-key HID reports.

## Build prerequisites

See Microsoft's [WDK download and compatibility guidance](https://learn.microsoft.com/en-us/windows-hardware/drivers/download-the-wdk) and [KMDF driver build tutorial](https://learn.microsoft.com/en-us/windows-hardware/drivers/gettingstarted/writing-a-kmdf-driver-based-on-a-template). The VHF architecture and report submission sequence are documented in [Write a HID source driver by using VHF](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/virtual-hid-framework--vhf-).

1. Windows 10 or 11, x64.
2. Visual Studio with **Desktop development with C++**. Microsoft currently pairs the latest WDK with Visual Studio 2026; for Visual Studio 2022, use the compatible WDK version listed in Microsoft's current download guidance.
3. The Windows Driver Kit (WDK) integration and a matching Windows SDK.
4. A Windows test machine or VM. Kernel-driver installation and test-signing changes should not be done casually on a daily-use machine.

Open `NativeInputsVhf.vcxproj` in Visual Studio and select **Release / x64**, then build. The project expects the WDK to provide `vhf.h`, KMDF headers, `VhfKm.lib`, and the kernel-mode build tools. If Visual Studio reports that the `WindowsKernelModeDriver10.0` toolset is missing, repair the WDK/Visual Studio integration rather than substituting a user-mode compiler.

The build output is placed under `bin\Release`. Verify that it contains `NativeInputsVhf.sys`, `NativeInputsVhf.inf`, and `NativeInputsVhf.cat` before installing. If your WDK version does not automatically produce the catalog, generate it with the WDK `Inf2Cat` tool for Windows x64.

## Driver signing and installation

Windows requires kernel-mode drivers to satisfy its code-signing policy. A locally built development driver normally needs a test-signed package and a test environment configured to accept it. Test-signing mode can be incompatible with Secure Boot and some virtualization-based security configurations. This repository intentionally does **not** change boot configuration, disable Secure Boot, or install a certificate automatically.

Read Microsoft's [test-signing boot option](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/the-testsigning-boot-configuration-option), [test-signed package installation](https://learn.microsoft.com/en-us/windows-hardware/drivers/install/installing-test-signed-driver-packages), and [driver-signing guide](https://learn.microsoft.com/en-us/windows-hardware/drivers/develop/signing-a-driver) for your exact Windows build. Enabling test signing can require Secure Boot changes and a restart; it can also interact with BitLocker and Memory Integrity/HVCI. Do not change those protections on your primary machine just to try this driver. Do not install an unsigned or untrusted kernel driver. Once the package is correctly signed and Windows is configured to accept the signature:

1. Open an **Administrator** terminal in `bin\Release` (or the folder containing the built INF, CAT, and SYS files).
2. Use the WDK `devcon.exe` matching your host architecture to create the root-enumerated device:

   ```powershell
   devcon.exe install .\NativeInputsVhf.inf Root\NativeInputsVhf
   ```

3. Confirm that the device starts without an error in Device Manager. The driver creates the control path `\\.\NativeInputsVhf` and enumerates the child HID keyboard and mouse devices.
4. Run Python from an **Administrator** terminal. The source-driver control interface is deliberately restricted to LocalSystem and Administrators.

To remove the root device, use an Administrator terminal:

```powershell
devcon.exe remove "Root\NativeInputsVhf"
```

Then remove the associated driver package from the Driver Store with `pnputil /delete-driver oemNN.inf /uninstall` after identifying its published name with `pnputil /enum-drivers`. Do not delete a package used by another device.

## Python usage

Install the project in editable mode from the repository root:

```powershell
py -m pip install -e .
```

Then run this from an elevated PowerShell window:

```python
from native_keyboard_inputs import InputController

with InputController("windows_vhf") as inputs:
    inputs.keyboard.tap("a")
    inputs.keyboard.hotkey("ctrl", "shift", "esc")
    inputs.mouse.move_relative(80, 0)
    inputs.mouse.click("left")
    inputs.mouse.scroll(vertical=2)
```

Or configure the process-wide API:

```python
from native_keyboard_inputs import configure, keyboard, mouse, close

configure("windows_vhf")
keyboard.tap("space")
mouse.move_relative(0, 40)
close()
```

Keep the `InputController` context manager or call `close()` so held keys/buttons are released. A forced process termination or system crash can still interrupt normal cleanup.

## Verification

After installation, check Device Manager under **Keyboards** and **Mice and other pointing devices** for the VHF child devices. You can also run:

```powershell
pnputil /enum-devices /connected /class HIDClass
```

The project can run its Python unit tests on non-Windows hosts because the report encoders are pure Python:

```powershell
py -m unittest discover -s tests -v
```

The KMDF project itself must be built and exercised on Windows with the WDK. It has not been compiled or hardware/OS-tested in this Linux environment.
