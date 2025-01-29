import os



# def skipif_platform(args: str):
#     """平台跳过
#     skipif_platform-aarch64
#     """
#     _skip_key = args.split("&")
#     for key in _skip_key:
#         if setting.SYS_ARCH == key:
#             return True
#     return False
#
#
# def skipif_not_platform(args: str):
#     """平台不跳过
#     skipif_not_platform-aarch64
#     """
#     return not skipif_platform(args)
#
#
# def skipif_xdg_type(args: str):
#     """skipif wayland or x11
#     skipif_xdg_type-wayland
#     """
#     _skip_key = args.split("&")
#     for key in _skip_key:
#         if setting.DISPLAY_SERVER == key:
#             return True
#     return False
#
#
# def skipif_cpu_name(args: str):
#     """skipif cpu name
#     使用 sudo dmidecode -s system-product-name 查看机器的cpu型号
#     剔除中横线和&符号，比如：KLVV-W5821，标签记录为 KLVVW5821
#     skipif_cpu_name-KLVVW5821
#     """
#     _skip_key = args.split("&")
#     for key in _skip_key:
#         if (
#                 os.popen(
#                     f"echo '{setting.PASSWORD}'| "
#                     "sudo -S dmidecode -s system-product-name | awk '{print $NF}'"
#                 )
#                         .read()
#                         .split("\n")[0]
#                         .replace("-", "")
#                         .replace("&", "")
#                 == key
#         ):
#             return True
#     return False
#
#
# def skipif_not_cpu_name(args: str):
#     """skipif not cpu name
#     使用 sudo dmidecode -s system-product-name 查看机器的cpu型号
#     剔除中横线和&符号，比如：KLVV-W5821，标签记录为 KLVVW5821
#     skipif_not_cpu_name-KLVVW5821
#     """
#     return not skipif_cpu_name(args)
#
#
# def skipif_os_version(args: str):
#     """
#     系统版本跳过
#     skipif_os_version-1060
#     """
#     _skip_key = args.split("&")
#     for key in _skip_key:
#         if key == setting.version_cfg.get("MinorVersion"):
#             return True
#     return False
#
#
# def skipif_not_os_version(args: str):
#     """
#     系统版本不跳过
#     skipif_not_os_version-1060
#     """
#     return not skipif_os_version(args)