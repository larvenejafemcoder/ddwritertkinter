#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import os
import queue
import re
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import tkinter as tk
from tkinter import filedialog, messagebox, ttk



MEDIA_ROOTS = ("/media", "/run/media")


def _iter_media_mount_dirs() -> List[str]:
    """
    Matches the behavior of the original Python implementation:
    - Look under /media, /run/media, /media/$USER, /run/media/$USER
    - Collect immediate subdirectories
    """
    username = os.environ.get("USER", "")
    candidates = [
        "/media",
        "/run/media",
        f"/media/{username}" if username else "/media",
        f"/run/media/{username}" if username else "/run/media",
    ]

    out: List[str] = []
    seen: set[str] = set()
    for base in candidates:
        try:
            if not (os.path.exists(base) and os.path.isdir(base)):
                continue
            for entry in os.listdir(base):
                p = os.path.join(base, entry)
                if os.path.isdir(p) and p not in seen:
                    seen.add(p)
                    out.append(p)
        except PermissionError:
            print(f"Permission denied accessing {base}")
        except Exception as err:
            print(f"Error accessing {base}: {err}")
    return out


def _read_proc_mounts() -> List[Tuple[str, str]]:
    """
    Return list of (device, mountpoint) from /proc/mounts.
    """
    mounts: List[Tuple[str, str]] = []
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    dev, mnt = parts[0], parts[1]
                    mounts.append((dev, mnt))
    except OSError as err:
        print(f"Error reading /proc/mounts: {err}")
    return mounts


def _lsblk_field(device_node: str, field: str) -> str:
    """
    Best-effort wrapper around lsblk calls used throughout the original project.
    """
    try:
        out = subprocess.check_output(
            ["lsblk", "-d", "-n", "-o", field, device_node],
            text=True,
            timeout=5,
        ).strip()
        return out
    except Exception:
        return ""


def find_usb() -> Dict[str, str]:
    """
    Return dict where key = mount path and value = label (or directory name).
    Mirrors `drives/find_usb.py::find_usb()` output shape.
    """
    usbdict: Dict[str, str] = {}
    all_directories = _iter_media_mount_dirs()
    mounts = _read_proc_mounts()

    # Match by mountpoint equality to those directories
    targets = set(all_directories)
    for dev, mnt in mounts:
        if mnt in targets:
            label = _lsblk_field(dev, "LABEL").strip()
            if not label:
                label = os.path.basename(mnt)
            usbdict[mnt] = label
            print(f"Found USB: {mnt} -> {label}")
    return usbdict


def find_dn() -> Optional[str]:
    """
    Return the first device node backing a recognized media mount, or None.
    Mirrors `drives/find_usb.py::find_DN()`.
    """
    all_directories = _iter_media_mount_dirs()
    targets = set(all_directories)
    for dev, mnt in _read_proc_mounts():
        if mnt in targets:
            return dev
    return None


def _parent_block_device(device_node: str) -> Optional[str]:
    """
    Given /dev/sdb1 -> /dev/sdb, and /dev/mmcblk0p1 -> /dev/mmcblk0.
    Uses /sys/class/block resolution similarly to the original codebase.
    """
    dev_name = os.path.basename(device_node)
    sys_class = Path("/sys/class/block") / dev_name
    try:
        parent_name = sys_class.resolve().parent.name
        if parent_name == dev_name:
            return device_node
        return f"/dev/{parent_name}"
    except OSError:
        return None


def resolve_device_node(mount_path: str) -> Optional[str]:
    """
    Resolve mount path -> underlying *disk* device node (parent block device).
    """
    normalized = os.path.normpath(mount_path)
    for dev, mnt in _read_proc_mounts():
        if os.path.normpath(mnt) == normalized:
            return _parent_block_device(dev) or dev
    return None


def is_removable_device(device_node: str) -> bool:
    """
    Safety check: confirm device is removable using /sys/block/<name>/removable.
    """
    disk_node = _parent_block_device(device_node) or device_node
    base_name = os.path.basename(disk_node)
    removable_path = Path("/sys/block") / base_name / "removable"
    try:
        return removable_path.read_text(encoding="utf-8").strip() == "1"
    except OSError:
        return False


def check_iso_signature(file_path: str) -> bool:
    """
    Validate ISO9660 Primary Volume Descriptor at sector 16.
    Offsets:
      32768: volume descriptor type (0x01 for PVD)
      32769-32773: standard identifier 'CD001'
      32774: version (0x01)
    """
    p = Path(file_path)
    if not p.is_file():
        print(f"Error: {file_path} is not a valid file. :(")
        return False

    try:
        with p.open("rb") as f:
            f.seek(32768)
            data = f.read(7)
            if len(data) < 7:
                print(f"Error: {file_path} is too small to contain a valid PVD. :(")
                return False

            vd_type, ident, version = data[0], data[1:6], data[6]
            if vd_type == 0x01 and ident == b"CD001" and version == 0x01:
                print(f"Valid ISO file: {file_path}")
                return True
            print(f"Error: {file_path} does not have a valid ISO9660 PVD signature. :(")
            return False
    except OSError as err:
        print(f"Error reading {file_path}: {err} :(")
        return False


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def check_sha256(file_path: str, expected_hash: str) -> bool:
    p = Path(file_path)
    if not p.is_file():
        print(f"Error: {file_path} is not a valid file. :( ")
        return False

    normalized_expected = expected_hash.strip().lower()
    if not _SHA256_RE.match(normalized_expected):
        print("Error: expected SHA256 hash must be exactly 64 hexadecimal characters.")
        return False

    sha256 = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        calculated = sha256.hexdigest()
        if calculated == normalized_expected:
            print(f"SHA256 hash matches for {file_path}")
            return True
        print(
            f"SHA256 hash mismatch for {file_path}: expected {normalized_expected}, got {calculated}"
        )
        print("You should not flash this ISO file, it may be corrupted or tampered with. :(")
        return False
    except OSError as err:
        print(f"Error reading {file_path}: {err} :(")
        return False


def flash_usb(iso_path: str, usb_mount_path: str) -> bool:
    """
    Flash ISO to a USB device via dd (destructive).
    Uses a removable-device check and ISO signature validation.
    """
    return write_image_dd(
        image_path=iso_path,
        usb_mount_path=usb_mount_path,
        validate_iso_signature=True,
    )


def write_image_dd(image_path: str, usb_mount_path: str, validate_iso_signature: bool) -> bool:
    """
    Generic image writing via `dd` (destructive).

    Major structural change vs original code: the old project only exposed ISO-flash,
    but the underlying mechanism is the same for raw images. This function supports
    writing any file; optional ISO signature validation can be toggled by the UI.
    """
    device_node = resolve_device_node(usb_mount_path)
    if not device_node:
        print(f"Could not resolve device node for mount path: {usb_mount_path}")
        return False

    raw_device = device_node  # already the parent disk if possible

    if not is_removable_device(raw_device):
        print(f"Aborting: {raw_device} is not a removable device.")
        return False

    dd_args = [
        "dd",
        f"if={image_path}",
        f"of={raw_device}",
        "bs=4M",
        "status=progress",
        "conv=fdatasync",
    ]
    print(f"Writing image with command: {' '.join(dd_args)}")

    try:
        if validate_iso_signature and not check_iso_signature(image_path):
            print(f"Aborting write: {image_path} does not look like a valid ISO file.")
            return False
        subprocess.run(dd_args, check=True)
        print(f"Successfully wrote {image_path} to {raw_device}")
        return True
    except PermissionError:
        print(f"Permission denied when trying to write image: {raw_device}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error during writing process: {e}")
        return False
    except Exception as err:
        print(f"Unexpected error during writing process: {err}")
        return False


def get_usb_info(usb_path: str) -> Dict[str, str]:
    """
    Mirrors `drives/get_usb_info.py::GetUSBInfo` output keys:
      device_node, label, mount_path
    """
    normalized = os.path.normpath(usb_path)
    device_node = resolve_device_node(normalized)
    if not device_node:
        print(f"Could not find device node for USB path: {usb_path}")
        return {}

    size_output = _lsblk_field(device_node, "SIZE").strip()
    # if SIZE isn't bytes, try again with -b
    if size_output and not size_output.isdigit():
        try:
            size_output = subprocess.check_output(
                ["lsblk", "-d", "-n", "-b", "-o", "SIZE", device_node],
                text=True,
                timeout=5,
            ).strip()
        except Exception:
            size_output = ""

    usb_size = int(size_output) if size_output.isdigit() else 0
    if usb_size > 32 * 1024**3:
        print(
            f"USB device is large, does user want to actually flash this?: {usb_size} bytes (passed 32 GB threshold)"
        )

    label = _lsblk_field(device_node, "LABEL").strip() or os.path.basename(usb_path)
    info = {"device_node": device_node, "label": label, "mount_path": usb_path}
    print(f"USB Info: {info}")
    return info


# Formatting / labeling (pkexec-based), mirroring drives/formatting.py


def _pkexec_not_found() -> None:
    print("Error: The command pkexec or labeling software was not found on your system.")


def _format_fail() -> None:
    print("Error: Formatting failed. Was the password correct? Is the drive unmounted?")


def _unexpected() -> None:
    print("An unexpected error occurred")


def _run_pkexec(args: List[str]) -> bool:
    """
    Equivalent shape to subprocess.run(..., check=True) with the original mapping:
    - FileNotFoundError -> pkexecNotFound
    - CalledProcessError -> FormatFail
    - other -> unexpected
    """
    try:
        subprocess.run(["pkexec", *args], check=True)
        return True
    except FileNotFoundError:
        _pkexec_not_found()
        return False
    except subprocess.CalledProcessError:
        _format_fail()
        return False
    except Exception:
        _unexpected()
        return False


def _run_pkexec_capture(args: List[str]) -> Optional[str]:
    try:
        cp = subprocess.run(
            ["pkexec", *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return cp.stdout.strip()
    except FileNotFoundError:
        _pkexec_not_found()
        return None
    except subprocess.CalledProcessError:
        _format_fail()
        return None
    except Exception:
        _unexpected()
        return None


def cluster() -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """
    Return (logical_block_size, physical_sector_size, sector_ratio).
    Note: the original Python had type bugs (dividing CompletedProcess objects);
    this uses the intended meaning by parsing stdout to integers.
    """
    drive = find_dn()
    if not drive:
        return None, None, None

    c1_s = _run_pkexec_capture(["blockdev", "--getbsz", drive])
    c2_s = _run_pkexec_capture(["blockdev", "--getbss", drive])
    if not c1_s or not c2_s:
        return None, None, None

    try:
        c1 = int(c1_s)
        c2 = int(c2_s)
        sector = int(c1 / c2) if c2 else 0
        return c1, c2, sector
    except Exception:
        _unexpected()
        return None, None, None


def volumecustomlabel(fs_type: int, new_label: str) -> bool:
    mount_dict = find_usb()
    if not mount_dict:
        return False
    mount = next(iter(mount_dict))
    drive = find_dn()
    if not drive:
        return False

    if not _run_pkexec(["umount", drive]):
        return False

    ok = False
    if fs_type == 0:
        ok = _run_pkexec(["ntfslabel", drive, new_label])
    elif fs_type in (1, 2):
        ok = _run_pkexec(["fatlabel", drive, new_label])
    elif fs_type == 3:
        ok = _run_pkexec(["e2label", drive, new_label])
    else:
        _unexpected()
        ok = False

    if not ok:
        return False

    return _run_pkexec(["mount", drive, mount])


def dskformat(fs_type: int) -> bool:
    c1, _c2, sector = cluster()
    mount_dict = find_usb()
    if not mount_dict:
        return False
    mount = next(iter(mount_dict))

    if c1 is None or sector is None:
        return False

    clusters = str(c1)
    sectors = str(sector)

    if fs_type == 0:
        ok = _run_pkexec(["mkfs.ntfs", "-c", clusters, "-Q", mount])
        if ok:
            print("success format to ntfs!")
        return ok
    if fs_type == 1:
        ok = _run_pkexec(["mkfs.vfat", "-s", sectors, "-F", "32", mount])
        if ok:
            print("success format to fat32!")
        return ok
    if fs_type == 2:
        ok = _run_pkexec(["mkfs.exfat", "-b", clusters, mount])
        if ok:
            print("success format to exFAT!")
        return ok
    if fs_type == 3:
        ok = _run_pkexec(["mkfs.ext4", "-b", clusters, mount])
        if ok:
            print("success format to ext4!")
        return ok

    _unexpected()
    return False


# Original stubs are preserved as no-ops
def quickformat() -> None:
    pass


def createextended() -> None:
    pass


def checkdevicebadblock() -> None:
    pass


# -----------------------------
# Tkinter UI
# -----------------------------


@dataclass
class UsbChoice:
    mount_path: str
    label: str

    def display(self) -> str:
        return f"{self.label} ({self.mount_path})"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ddwriter proj - LarveneJafemCoder")
        self.geometry("860x620")

        self._usb_choices: List[UsbChoice] = []
        self._log_queue: "queue.Queue[str]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None

        self._build_ui()
        self._refresh_usb_list()
        self.after(100, self._drain_log_queue)

    def _build_ui(self) -> None:
        # Try to loosely echo the classic Rufus layout:
        #   - Drive properties
        #   - Boot selection
        #   - Format options
        #   - Status + Start/Close
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # --- Drive properties ---
        drive_frame = ttk.LabelFrame(self, text="Drive properties", padding=10)
        drive_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        drive_frame.columnconfigure(1, weight=1)

        ttk.Label(drive_frame, text="Device").grid(row=0, column=0, sticky="w")
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(drive_frame, textvariable=self.device_var, state="readonly")
        self.device_combo.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        ttk.Button(drive_frame, text="Refresh", command=self._refresh_usb_list).grid(
            row=1, column=2, padx=(8, 0)
        )

        # --- Boot selection (image path + ISO-related helpers) ---
        boot_frame = ttk.LabelFrame(self, text="Boot selection", padding=10)
        boot_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(8, 0))
        boot_frame.columnconfigure(1, weight=1)

        ttk.Label(boot_frame, text="Disk or ISO image").grid(row=0, column=0, sticky="w")
        self.iso_var = tk.StringVar()
        self.iso_entry = ttk.Entry(boot_frame, textvariable=self.iso_var)
        self.iso_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        ttk.Button(boot_frame, text="SELECT", command=self._browse_iso).grid(
            row=1, column=2, padx=(8, 0)
        )

        ttk.Label(boot_frame, text="SHA256 (optional)").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.sha_var = tk.StringVar()
        self.sha_entry = ttk.Entry(boot_frame, textvariable=self.sha_var)
        self.sha_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 0))
        ttk.Button(boot_frame, text="Check SHA", command=self._check_sha).grid(
            row=3, column=2, padx=(8, 0)
        )

        self.validate_iso_var = tk.IntVar(value=1)
        ttk.Checkbutton(
            boot_frame,
            text="Validate ISO signature before dd (recommended for .iso)",
            variable=self.validate_iso_var,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        # --- Middle section: format options + helper actions ---
        mid = ttk.Frame(self, padding=10)
        mid.grid(row=2, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(1, weight=1)

        fmt = ttk.LabelFrame(mid, text="Format options", padding=10)
        fmt.grid(row=0, column=0, sticky="ew")
        fmt.columnconfigure(1, weight=1)

        ttk.Label(fmt, text="Volume label").grid(row=0, column=0, sticky="w")
        self.label_var = tk.StringVar(value="Volume Label")
        self.label_entry = ttk.Entry(fmt, textvariable=self.label_var)
        self.label_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 6))

        ttk.Label(fmt, text="File system").grid(row=2, column=0, sticky="w")
        self.fs_var = tk.StringVar(value="NTFS")
        self.fs_combo = ttk.Combobox(
            fmt,
            textvariable=self.fs_var,
            state="readonly",
            values=["NTFS", "FAT32", "exFAT", "ext4"],
            width=10,
        )
        self.fs_combo.grid(row=3, column=0, sticky="w", pady=(2, 0))

        ttk.Label(fmt, text="Cluster size").grid(row=2, column=1, sticky="w")
        self.cluster_var = tk.StringVar(value="4096 bytes (default)")
        self.cluster_combo = ttk.Combobox(
            fmt,
            textvariable=self.cluster_var,
            state="readonly",
            values=["4096 bytes (default)", "8192 bytes", "16384 bytes"],
        )
        self.cluster_combo.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(2, 0))

        helpers = ttk.Frame(fmt)
        helpers.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(helpers, text="USB Info", command=self._usb_info).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(helpers, text="Check ISO", command=self._check_iso).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(helpers, text="Write image (dd)", command=self._flash).grid(row=0, column=2)

        ttk.Button(fmt, text="Format", command=self._format).grid(
            row=5, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Button(fmt, text="Set label", command=self._set_label).grid(
            row=5, column=1, sticky="w", pady=(8, 0)
        )
        ttk.Button(fmt, text="Cluster info", command=self._cluster_info).grid(
            row=5, column=2, sticky="w", pady=(8, 0)
        )

        status = ttk.LabelFrame(mid, text="Status", padding=10)
        status.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        status.columnconfigure(0, weight=1)
        status.rowconfigure(0, weight=1)

        self.log = tk.Text(status, height=10, wrap="word")
        self.log.grid(row=0, column=0, sticky="nsew")
        self.log.configure(state="disabled")

        self.progress = ttk.Progressbar(status, mode="indeterminate")
        self.progress.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        footer = ttk.Frame(self, padding=10)
        footer.grid(row=3, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        ttk.Label(
            footer,
            text="WARNING: Writing or formatting will erase all data on the selected device.",
        ).grid(row=0, column=0, sticky="w")

        btn_row = ttk.Frame(footer)
        btn_row.grid(row=0, column=1, sticky="e")
        ttk.Button(btn_row, text="START", command=self._flash).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(btn_row, text="CLOSE", command=self.destroy).grid(row=0, column=1)

    # ---- UI helpers ----

    def _log_line(self, msg: str) -> None:
        self._log_queue.put(msg)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", msg + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()

    def _selected_mount(self) -> Optional[str]:
        s = self.device_var.get().strip()
        if not s:
            return None
        m = re.search(r"\((.+)\)\s*$", s)
        return m.group(1) if m else None

    def _fs_type(self) -> int:
        val = self.fs_var.get()
        return {"NTFS": 0, "FAT32": 1, "exFAT": 2, "ext4": 3}.get(val, 0)

    # ---- Actions ----

    def _refresh_usb_list(self) -> None:
        devices = find_usb()
        self._usb_choices = [UsbChoice(mnt, lbl) for mnt, lbl in devices.items()]
        values = [c.display() for c in self._usb_choices]
        self.device_combo["values"] = values
        if values:
            self.device_combo.current(0)
        else:
            self.device_var.set("")
        self._log_line(f"Detected USB devices: {devices}")

    def _browse_iso(self) -> None:
        path = filedialog.askopenfilename(
            title="Select image",
            filetypes=[
                ("Disk images", "*.iso *.img *.raw *.bin"),
                ("ISO images", "*.iso"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.iso_var.set(path)
            base = os.path.basename(path)
            if base.lower().endswith(".iso"):
                self.label_var.set(base[:-4].upper() or "Volume Label")
            self._log_line(f"Selected image: {path}")

    def _usb_info(self) -> None:
        mount = self._selected_mount()
        if not mount:
            messagebox.showerror("USB Info", "Select a USB device first.")
            return
        info = get_usb_info(mount)
        if not info:
            messagebox.showerror("USB Info", "Could not fetch USB info.")
            return
        messagebox.showinfo("USB Info", "\n".join(f"{k}: {v}" for k, v in info.items()))

    def _check_iso(self) -> None:
        iso = self.iso_var.get().strip()
        if not iso:
            messagebox.showerror("Check ISO", "Select an ISO file first.")
            return
        ok = check_iso_signature(iso)
        messagebox.showinfo("Check ISO", "Valid ISO signature." if ok else "Invalid ISO signature.")

    def _check_sha(self) -> None:
        iso = self.iso_var.get().strip()
        h = self.sha_var.get().strip()
        if not iso or not h:
            messagebox.showerror("Check SHA256", "Provide both ISO path and expected SHA256.")
            return
        ok = check_sha256(iso, h)
        messagebox.showinfo("Check SHA256", "SHA256 matches." if ok else "SHA256 does not match.")

    def _run_in_worker(self, title: str, fn) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showwarning("Busy", "An operation is already running.")
            return

        def work() -> None:
            self._log_line(f"--- {title} ---")
            ok = False
            err: Optional[str] = None
            try:
                ok = bool(fn())
            except Exception as e:
                err = str(e)
            finally:
                self.after(0, lambda: self._set_busy(False))
                if err:
                    self._log_line(f"{title} failed: {err}")
                    self.after(0, lambda: messagebox.showerror(title, err))
                else:
                    self._log_line(f"{title}: {'OK' if ok else 'FAILED'}")
                    self.after(
                        0,
                        lambda: messagebox.showinfo(
                            title, "Operation completed successfully." if ok else "Operation failed."
                        ),
                    )

        self._set_busy(True)
        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _flash(self) -> None:
        mount = self._selected_mount()
        iso = self.iso_var.get().strip()
        if not mount or not iso:
            messagebox.showerror("Write image", "Select a USB device and an image file first.")
            return

        if not Path(iso).is_file():
            messagebox.showerror("Write image", "Image path is not a file.")
            return

        dev = resolve_device_node(mount) or "<unknown>"
        if not messagebox.askyesno(
            "Confirm write",
            f"This will ERASE data on {dev}.\n\nContinue?",
        ):
            return

        validate = bool(self.validate_iso_var.get())
        self._run_in_worker(
            "Write image (dd)",
            lambda: write_image_dd(iso, mount, validate_iso_signature=validate),
        )

    def _format(self) -> None:
        mount = self._selected_mount()
        if not mount:
            messagebox.showerror("Format", "Select a USB device first.")
            return
        fs_type = self._fs_type()
        dev = resolve_device_node(mount) or "<unknown>"
        if not messagebox.askyesno(
            "Confirm format",
            f"This will FORMAT (erase) the selected device.\n\nTarget: {dev}\nFilesystem: {self.fs_var.get()}\n\nContinue?",
        ):
            return
        self._run_in_worker("Format", lambda: dskformat(fs_type))

    def _set_label(self) -> None:
        mount = self._selected_mount()
        if not mount:
            messagebox.showerror("Set label", "Select a USB device first.")
            return
        label = self.label_var.get().strip()
        if not label:
            messagebox.showerror("Set label", "Provide a label.")
            return
        fs_type = self._fs_type()
        self._run_in_worker("Set label", lambda: volumecustomlabel(fs_type, label))

    def _cluster_info(self) -> None:
        c1, c2, sec = cluster()
        if c1 is None:
            messagebox.showerror("Cluster info", "Could not read cluster info.")
            return
        messagebox.showinfo(
            "Cluster info",
            f"Logical block size: {c1}\nPhysical sector size: {c2}\nSector ratio: {sec}",
        )


def main() -> None:
    try:
        app = App()
        app.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

