
# dd image writer

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status: Beta](https://img.shields.io/badge/status-beta-orange)

## 🚧 Beta Release

**dd image writer** is currently in **Beta**.

It is a physical drive imaging utility written in Python. In practical terms, it is a graphical frontend for `dd`, the classic Unix disk duplicator.

Core functionality works, but the project is still under active development. Expect:

* Bugs
* Missing features
* Internal refactors
* UI changes

If you need a production-grade, battle-tested tool, use established alternatives for now. This project is evolving.

---

## What It Does

dd image writer is a graphical wrapper around `dd` that helps you write disk images to USB drives more safely and transparently.

It can:

* 🔍 Discover USB devices on your system
* 💿 Write image files (ISO, IMG, etc.) using `dd`
* 🔐 Validate ISO signatures before writing (optional but recommended)
* 🧮 Verify SHA256 hashes for image integrity
* 🗂 Format USB drives (FAT32, exFAT, NTFS, ext4)
* 📊 Display detailed drive information before destructive actions

It does not replace `dd`. It simply gives it a graphical interface and safety checks.

---

# Quick Start (Beginner Friendly)

This section assumes:

* You are new to Python
* You are new to Git
* You just want to run the GUI on Linux

---

## Current Prototype: Tkinter (Single File)

The current GUI prototype is:

```
tkinter_gui/main.py
```

It uses:

* Tkinter (built into Python)
* Common Linux system tools:

  * `/proc`, `/sys`, `lsblk` for device discovery
  * `dd` for writing
  * `pkexec` + `mkfs.*` tools for formatting

---

## 1️⃣ Install the Basics (One-Time Setup)

### Check Python

```bash
python3 --version
```

You need **Python 3.10 or newer**.

If not installed:

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
```

### Fedora

```bash
sudo dnf install python3 python3-venv python3-pip git
```

### Arch / Manjaro

```bash
sudo pacman -Syu python python-virtualenv python-pip git
```

---

### Check Git

```bash
git --version
```

If you installed using the commands above, Git is already included.

---

## 2️⃣ Clone the Repository

Open a terminal:

```bash
cd ~
git clone https://github.com/hog185/dd-image-writer.git
cd dd-image-writer
```

Verify files:

```bash
ls
```

You should see:

* `README.md`
* `tkinter_gui/`
* `src/`

---

## 3️⃣ Create a Virtual Environment (Recommended)

This keeps your system Python clean.

### Create (once per clone)

```bash
python3 -m venv .venv
```

### Activate (every new terminal session)

```bash
source .venv/bin/activate
```

If successful, your prompt usually shows:

```
(.venv)
```

### Deactivate

```bash
deactivate
```

---

## 4️⃣ Dependencies

### Python Dependencies

For the Tkinter prototype:

* No pip packages required
* Tkinter is part of the Python standard library

---

### Required System Tools

Always required:

* `lsblk` (from util-linux)
* `dd` (from coreutils)

Required for formatting features:

* `pkexec` (Polkit)

Filesystem tools (install only what you need):

| Filesystem | Tools                    | Common Package |
| ---------- | ------------------------ | -------------- |
| FAT32      | `mkfs.vfat`, `fatlabel`  | dosfstools     |
| exFAT      | `mkfs.exfat`             | exfatprogs     |
| NTFS       | `mkfs.ntfs`, `ntfslabel` | ntfs-3g        |
| ext4       | `mkfs.ext4`, `e2label`   | e2fsprogs      |

---

## 5️⃣ Run the Application

```bash
python tkinter_gui/main.py
```

Expected behavior:

* Terminal prints detected USB devices
* A window opens titled:

```
dd image writer (Tkinter prototype)
```

If USB drives are connected, they appear in the **Device dropdown**.

For a safe test:

* Click **Refresh**
* Click **USB Info**
* Click **Check ISO signature**
* Close the window

You do NOT need to write anything to test the UI.

---

## 6️⃣ Button Reference (Tkinter Prototype)

### Refresh

Re-detect USB devices under:

* `/media`
* `/run/media`

### USB Info

Displays:

* device_node
* label
* mount_path

### Check ISO Signature

Validates ISO9660 Primary Volume Descriptor (sector 16).

### Check SHA

Compares SHA256 of selected image to expected value.

### Write Image (dd)

Writes selected image file to selected USB device.

Checkbox:
**Validate ISO signature before dd**

* ON → refuses invalid ISO files
* OFF → writes any file (use for raw `.img`)

---

### Format (Destructive)

Uses:

* `pkexec`
* `mkfs.*`

Erases entire device.

---

### Set Label

* Unmounts device
* Sets filesystem label
* Mounts again

---

### Cluster Info

Uses `pkexec blockdev` to read block sizes and compute cluster information.

---

# ⚠️ Safety Warning

This is a drive imaging tool.

The following actions permanently destroy data:

* Write image (dd)
* Format

Before clicking anything destructive:

1. Double-check the selected device.
2. Confirm the device node using **USB Info**.
3. Make sure it is your USB stick and not your main drive.

If unsure, stop.

Exploring the UI without writing is completely safe.

---

## 8️⃣ Exit & Cleanup

Close the window to exit.

Deactivate virtual environment:

```bash
deactivate
```

Delete the project entirely:

```bash
rm -rf ~/dd-image-writer
```

Make sure the virtual environment is deactivated first.


