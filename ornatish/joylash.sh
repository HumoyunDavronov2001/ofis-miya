#!/usr/bin/env bash
# MIYA — serverga joylash (shu kompyuterdan). Ishlatish:
#   ornatish/joylash.sh miya.DOMEN.uz [miyaapi.DOMEN.uz] [--malumot]   # domen(lar); --malumot — birinchi marta mahalliy baza
#   ornatish/joylash.sh                           # keyingi yangilashlar (domen serverda saqlanadi, baza tegilmaydi)
# Server: MIYA_SERVER=root@SERVER_IP (majburiy). Sinovlar, dizayn namunasi va mahalliy ma'lumot yuborilmaydi.
# DIQQAT: bitta bot tokeni faqat bitta joyda ishlaydi — --malumot bilan joylangach mahalliy MIYA to'xtatiladi.
set -u
SERVER=${MIYA_SERVER:?MIYA_SERVER=root@SERVER_IP berilishi kerak}
DOMEN=""
API=""
MALUMOT=0
for a in "$@"; do
  case "$a" in
    --malumot) MALUMOT=1 ;;
    *) if [ -z "$DOMEN" ]; then DOMEN="$a"; else API="$a"; fi ;;
  esac
done
cd "$(dirname "$0")/.."
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=15 "$SERVER")

echo "1/5 Avtomatik sinovlar..."
if ! python3 -m pytest -q sinov > /tmp/miya-sinov.log 2>&1; then
  tail -20 /tmp/miya-sinov.log
  echo "Sinovlar o'tmadi — joylanmaydi."; exit 1
fi
tail -1 /tmp/miya-sinov.log | sed 's/^/    /'

echo "2/5 Serverga yuborilmoqda..."
"${SSH[@]}" "rm -rf /opt/miya.yangi && mkdir -p /opt/miya.yangi /root/miya-yuklash" || { echo "Serverga ulanib bo'lmadi."; exit 1; }
rsync -az --delete --exclude malumot/ --exclude sinov/ --exclude __pycache__/ --exclude '*.pyc' --exclude ornatish/.env \
  --exclude 'dizayn/*.png' --exclude 'dizayn/*.html' -e "ssh -o BatchMode=yes" ./ "$SERVER:/opt/miya.yangi/" \
  || { echo "Fayllar yuborilmadi."; exit 1; }
if [ -n "$DOMEN" ]; then
  for d in "$DOMEN" $API; do
    echo "$d" | grep -qE '^[a-z0-9.-]+\.[a-z]{2,}$' || { echo "Domen noto'g'ri: $d"; exit 1; }
  done
  "${SSH[@]}" "printf 'MIYA_DOMEN=%s\nMIYA_API_DOMEN=%s\n' '$DOMEN' '$API' > /opt/miya.yangi/ornatish/.env"
else
  "${SSH[@]}" "cp /opt/miya/ornatish/.env /opt/miya.yangi/ornatish/.env" \
    || { echo "Birinchi joylashda domenni bering: ornatish/joylash.sh miya.DOMEN.uz --malumot"; exit 1; }
fi
if [ "$MALUMOT" = 1 ]; then
  TMP=$(mktemp -d)
  python3 - "$TMP/miya.db" <<'PY' || { echo "Mahalliy bazadan nusxa olinmadi."; exit 1; }
import sqlite3, sys
manba = sqlite3.connect("malumot/miya.db")
nusxa = sqlite3.connect(sys.argv[1])
manba.backup(nusxa)
nusxa.execute("PRAGMA journal_mode=DELETE")
nusxa.close()
PY
  cp malumot/.kalit "$TMP/.kalit" 2>/dev/null
  "${SSH[@]}" "mkdir -p /root/miya-yuklash/boshlangich && chmod 700 /root/miya-yuklash/boshlangich"
  rsync -a -e "ssh -o BatchMode=yes" "$TMP/" "$SERVER:/root/miya-yuklash/boshlangich/" || { rm -rf "$TMP"; echo "Baza yuborilmadi."; exit 1; }
  rm -rf "$TMP"
  echo "    mahalliy baza yuborildi (serverda baza bo'lmasa ishlatiladi)"
fi

echo "3/5 Serverda yig'ilmoqda (fonda — SSH uzilsa ham davom etadi)..."
"${SSH[@]}" "rm -f /root/miya-yuklash/tayyor /root/miya-yuklash/xato && \
  setsid nohup bash /opt/miya.yangi/ornatish/serverda.sh > /root/miya-yuklash/nohup.log 2>&1 < /dev/null &"
for _ in $(seq 160); do
  sleep 5
  if "${SSH[@]}" "test -f /root/miya-yuklash/tayyor"; then echo "    tayyor"; break; fi
  if "${SSH[@]}" "test -f /root/miya-yuklash/xato"; then
    echo "XATO: $("${SSH[@]}" "cat /root/miya-yuklash/xato")"
    "${SSH[@]}" "tail -30 /root/miya-yuklash/jurnal"
    exit 1
  fi
done
"${SSH[@]}" "test -f /root/miya-yuklash/tayyor" || { echo "13 daqiqada tugamadi — serverdagi /root/miya-yuklash/jurnal ni ko'ring."; exit 1; }

echo "4/5 Mahalliy MIYA..."
if [ "$MALUMOT" = 1 ]; then
  P=$(ss -ltnp 2>/dev/null | grep ':8090 ' | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -1)
  if [ -n "$P" ] && tr '\0' ' ' < "/proc/$P/cmdline" 2>/dev/null | grep -q -- '-m miya'; then
    kill "$P" && echo "    mahalliy MIYA to'xtatildi (bot endi faqat serverda ishlaydi)"
  else
    echo "    mahalliy MIYA ishlamayapti"
  fi
else
  echo "    o'zgarmadi"
fi

[ "$MALUMOT" = 1 ] && "${SSH[@]}" "sed -n 's/^MIYA_DOMEN=//p' /opt/miya/ornatish/.env" > malumot/.serverda  # ishga_tushir.sh qo'riqchisi

echo "5/5 Domen holati..."
for D in $("${SSH[@]}" "sed -n 's/^MIYA_DOMEN=//p; s/^MIYA_API_DOMEN=//p' /opt/miya/ornatish/.env"); do
  [ -n "$D" ] || continue
  if getent ahostsv4 "$D" > /dev/null; then
    KOD=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$D/api/holat" || true)
    echo "    https://$D → $KOD (Caddy qorovuli blokni 5 daqiqagacha ichida qo'shadi, sertifikat shundan keyin)"
  else
    echo "    $D uchun DNS yozuvi hali yo'q: A yozuv → $(echo "$SERVER" | sed 's/.*@//'). Yozuv qo'shilgach qorovul o'zi ulaydi."
  fi
done
