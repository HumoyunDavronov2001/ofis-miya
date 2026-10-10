#!/usr/bin/env bash
# MIYA — ofis xotirasi. Ishga tushirish: ./ishga_tushir.sh  (panel: http://127.0.0.1:8090)
# Dastur serverga ko'chirilgan bo'lsa (malumot/.serverda) — mahalliy ishga tushmaydi: bitta bot tokeni ikki joyda
# ishlasa Telegram xabarlari yo'qoladi (409). Baribir kerak bo'lsa: MIYA_MAHALLIY=1 ./ishga_tushir.sh
cd "$(dirname "$0")" || exit 1
if [ -f malumot/.serverda ] && [ "${MIYA_MAHALLIY:-0}" != 1 ]; then
  echo "MIYA serverda ishlayapti: https://$(cat malumot/.serverda) — mahalliy nusxa ishga tushirilmadi."
  echo "Baribir kerak bo'lsa (avval serverdagi botni to'xtating): MIYA_MAHALLIY=1 ./ishga_tushir.sh"
  exit 1
fi
exec python3 -m miya --port "${MIYA_PORT:-8090}" "$@"
