"""Teams 연동 설정 도우미.

    venv/bin/python teams_setup.py             # 현재 연결 상태 점검 + 동기화 폴더 후보 찾기
    venv/bin/python teams_setup.py --set PATH  # 채널 폴더(OneDrive 동기화 경로) 지정
"""
from __future__ import annotations

import argparse
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(BASE, "config.json")
CLOUD = os.path.expanduser("~/Library/CloudStorage")


def candidates(max_depth: int = 3) -> list[str]:
    """OneDrive로 동기화된 SharePoint/Teams 폴더 후보."""
    out = []
    if not os.path.isdir(CLOUD):
        return out
    for root, dirs, _ in os.walk(CLOUD):
        depth = root[len(CLOUD):].count(os.sep)
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if depth >= max_depth:
            dirs[:] = []
        if depth >= 1 and ("SharedLibraries" in root or "ai" in os.path.basename(root).lower()):
            out.append(root)
    return out


def load_env_keys() -> dict:
    keys = {}
    path = os.path.join(BASE, ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", help="채널 파일 폴더의 로컬 동기화 경로")
    args = ap.parse_args()
    cfg = json.load(open(CFG, encoding="utf-8"))
    tcfg = cfg.setdefault("teams", {})

    if args.set:
        path = os.path.expanduser(args.set)
        if not os.path.isdir(path) or not os.access(path, os.W_OK):
            print(f"✗ 쓰기 가능한 폴더가 아닙니다: {path}")
            return 1
        tcfg["sync_dir"] = path
        tmp = CFG + ".tmp"
        json.dump(cfg, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.replace(tmp, CFG)
        print(f"✓ 채널 폴더 설정: {path}")

    print("\n[Teams 연결 상태]")
    sd = os.path.expanduser(tcfg.get("sync_dir", "") or "")
    print(f"  채널 파일 폴더 : {'✓ ' + sd if sd and os.path.isdir(sd) else '✗ 미설정'}")
    wh = load_env_keys().get("TEAMS_WEBHOOK_URL", "")
    print(f"  채널 게시 웹훅 : {'✓ 설정됨' if wh.startswith('https://') else '✗ 미설정 (.env TEAMS_WEBHOOK_URL)'}")

    if not (sd and os.path.isdir(sd)):
        found = candidates()
        print("\n[동기화 폴더 후보]" if found else "\n동기화된 SharePoint 폴더가 아직 없습니다 (OneDrive 동기화 필요).")
        for c in found:
            print(f"  {c}")
        if found:
            print('\n  → 맞는 폴더로:  venv/bin/python teams_setup.py --set "<경로>"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
