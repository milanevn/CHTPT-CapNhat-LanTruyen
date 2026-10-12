"""Kiểm tra máy đã sẵn sàng chạy dự án chưa. Phụ trách: TV1.

Chạy từ thư mục gốc repo, ngay sau khi clone:
    python -m scripts.check_env            # kiểm tra máy mình
    python -m scripts.check_env --network  # khi demo nhiều laptop: thử kết nối tới các máy khác
"""

import argparse
import os
import socket
import sqlite3
import sys

MIN_PYTHON = (3, 10)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_results = []


def report(ok, title, hint=""):
    _results.append(ok)
    mark = "OK  " if ok else "LOI "
    print(f"[{mark}] {title}")
    if hint and not ok:
        print(f"       -> {hint}")


def warn(title, hint=""):
    print(f"[CHU Y] {title}")
    if hint:
        print(f"       -> {hint}")


def check_python():
    v = sys.version_info
    report(
        v >= MIN_PYTHON,
        f"Python {v.major}.{v.minor}.{v.micro} ({sys.executable})",
        "Cần Python 3.10 trở lên, nên dùng 3.12 giống CI. Trên Windows có thể chạy: py -3.12 -m scripts.check_env",
    )


def check_cwd():
    same = os.path.normcase(os.path.abspath(os.getcwd())) == os.path.normcase(REPO_ROOT)
    report(
        same,
        "Đang chạy từ thư mục gốc repo",
        f"cd vào {REPO_ROOT} rồi chạy lại bằng python -m ...",
    )


def check_path():
    lowered = REPO_ROOT.lower()
    if "onedrive" in lowered or "dropbox" in lowered or "google drive" in lowered:
        warn(
            "Repo đang nằm trong thư mục đồng bộ đám mây (OneDrive/Dropbox/Drive)",
            "Trình đồng bộ khóa file SQLite -> lỗi 'database is locked' hoặc hỏng dữ liệu. "
            "Clone lại vào thư mục thường, ví dụ C:\\code\\",
        )


def check_tkinter():
    try:
        import tkinter

        tcl = tkinter.Tcl()  # không mở cửa sổ
        report(True, f"Tkinter có sẵn (Tcl/Tk {tcl.eval('info patchlevel')})")
    except Exception as exc:  # ImportError hoặc TclError
        report(
            False,
            f"Thiếu Tkinter: {exc}",
            "Windows: chạy lại bộ cài Python > Modify > tick 'tcl/tk and IDLE'. Linux: cài gói python3-tk",
        )


def check_sqlite():
    try:
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE t (x INTEGER CHECK (x >= 0))")
        con.close()
        report(True, f"SQLite {sqlite3.sqlite_version}")
    except Exception as exc:
        report(False, f"SQLite lỗi: {exc}")


def check_data_dir_writable(cfg):
    from common import config

    folder = os.path.dirname(config.data_path(cfg, "S1"))
    probe_dir = os.path.dirname(folder)  # <repo>/data
    try:
        os.makedirs(probe_dir, exist_ok=True)
        probe = os.path.join(probe_dir, ".write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        report(True, f"Ghi được vào thư mục dữ liệu {probe_dir}")
    except OSError as exc:
        report(
            False,
            f"Không ghi được vào {probe_dir}: {exc}",
            "Kiểm tra quyền thư mục / antivirus",
        )


def load_config():
    try:
        from common import config
    except ImportError as exc:
        report(
            False,
            f"Không import được common.config: {exc}",
            "Chạy từ thư mục gốc repo bằng python -m",
        )
        return None
    path = config.resolve_path()
    try:
        cfg = config.load()
    except (OSError, ValueError) as exc:
        fix = (
            "Sửa hoặc xóa file cấu hình riêng này (mục 4.1 Hướng dẫn setup)"
            if path != config.CONFIG_PATH
            else "Lấy lại bản gốc: git restore common/config.json"
        )
        report(False, f"Cấu hình {path} lỗi: {exc}", fix)
        return None
    report(True, f"Đọc cấu hình: {os.path.relpath(path, REPO_ROOT)}")
    if path != config.CONFIG_PATH:
        warn(
            "Đang dùng cấu hình riêng thay cho common/config.json",
            "Xóa file đó (hoặc biến CHTPT_CONFIG) nếu muốn quay về mặc định",
        )
    return cfg


def _local_ips():
    ips = {"127.0.0.1", "localhost", "0.0.0.0"}
    try:
        ips.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:  # IP dùng để ra mạng (không gửi gói nào thật)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return ips


def _try_bind(host, port):
    """Thử mở cổng như máy chủ sẽ mở. Trả về None nếu được, hoặc thông báo lỗi."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(
            socket, "SO_EXCLUSIVEADDRUSE"
        ):  # Windows: không cho 2 tiến trình chung cổng
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        s.bind((host, port))
        s.listen(1)
        return None
    except OSError as exc:
        return exc
    finally:
        s.close()


def _someone_listening(host, port):
    """Có chương trình nào đang nghe ở host:port không (kể cả nghe trên mọi địa chỉ 0.0.0.0 / ::)."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _someone_listening(host, port):
    """Có chương trình nào đang nghe ở host:port không (kể cả nghe trên mọi địa chỉ 0.0.0.0 / ::)."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def check_ports(cfg):
    from common import config

    local = _local_ips()
    for node_id in config.NODE_IDS:
        host, port = config.address(cfg, node_id)
        if host not in local:
            continue  # máy này chạy trên laptop khác
        if _someone_listening(host, port):
            report(
                False,
                f"{node_id}: cổng {host}:{port} đang có chương trình khác nghe",
                "Máy chủ cũ chưa tắt, hoặc ứng dụng khác dùng cổng này. Windows: netstat -ano | findstr :%d "
                "rồi taskkill /PID <số> /F, hoặc đổi cổng trong config.local.json"
                % port,
            )
            continue
        err = _try_bind(host, port)
        if err is None:
            report(True, f"{node_id}: mở được cổng {host}:{port}")
            continue
        winerr = getattr(err, "winerror", None)
        if winerr == 10013:
            hint = (
                "Windows đã giữ cổng này (Hyper-V/WSL/Docker). Xem: "
                "netsh interface ipv4 show excludedportrange protocol=tcp  -> đổi cổng trong config.local.json"
            )
        elif winerr == 10048 or err.errno in (48, 98):
            hint = (
                "Cổng đang bị tiến trình khác chiếm (máy chủ cũ chưa tắt?). Windows: netstat -ano | findstr :%d"
                % port
            )
        elif winerr == 10049 or err.errno in (49, 99):
            hint = "IP trong cấu hình không phải IP của máy này (đổi Wi-Fi nên IP thay đổi?). Xem ipconfig"
        else:
            hint = ""
        report(False, f"{node_id}: không mở được {host}:{port} ({err})", hint)


def check_network(cfg):
    from common import config

    local = _local_ips()
    remote = [n for n in config.NODE_IDS if config.address(cfg, n)[0] not in local]
    if not remote:
        warn(
            "Cả 4 máy đều cấu hình trên máy này, không có máy từ xa để thử",
            "Demo nhiều laptop: sửa host trong common/config.local.json",
        )
        return
    for node_id in remote:
        host, port = config.address(cfg, node_id)
        try:
            with socket.create_connection((host, port), timeout=2):
                report(True, f"{node_id}: kết nối được {host}:{port}")
        except OSError as exc:
            report(
                False,
                f"{node_id}: không kết nối được {host}:{port} ({exc})",
                "Máy kia đã chạy server chưa? Hai máy cùng mạng chưa (Wi-Fi trường thường chặn máy-tới-máy, "
                "dùng hotspot điện thoại)? Máy kia đã cho Python qua Windows Firewall ở mạng Private chưa?",
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Kiểm tra môi trường chạy dự án")
    parser.add_argument(
        "--network", action="store_true", help="thử kết nối tới các máy ở laptop khác"
    )
    args = parser.parse_args(argv)

    print("== Kiểm tra môi trường ==")
    check_python()
    check_cwd()
    check_path()
    check_tkinter()
    check_sqlite()
    cfg = load_config()
    if cfg is not None:
        check_data_dir_writable(cfg)
        check_ports(cfg)
        if args.network:
            check_network(cfg)

    failed = _results.count(False)
    print()
    print(
        "Tất cả OK, máy đã sẵn sàng."
        if failed == 0
        else f"Có {failed} lỗi, sửa theo gợi ý ở trên rồi chạy lại."
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    # Console Windows đôi khi không in được tiếng Việt khi chuyển hướng ra file
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    sys.exit(main())
