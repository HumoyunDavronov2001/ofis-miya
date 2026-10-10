#!/bin/bash
# MIYA — serverning o'zida o'rnatish/yangilash (joylash.sh fonda chaqiradi; SSH uzilsa ham davom etadi).
# /opt/miya.yangi → /opt/miya; eski versiya /opt/miya.eski da qoladi. Sog'lom bo'lmasa — eski versiyaga qaytadi.
# Ma'lumot (baza, .kalit, fayllar) miya_malumot hajmida — yangilashda tegilmaydi.
# Birinchi o'rnatishda /root/miya-yuklash/boshlang'ich/ da baza bo'lsa va hajm bo'sh bo'lsa — o'sha ko'chiriladi.
# Natija belgisi: /root/miya-yuklash/tayyor yoki /root/miya-yuklash/xato (ichida sabab).
set -u
YANGI=/opt/miya.yangi
JORIY=/opt/miya
ESKI=/opt/miya.eski
B=/root/miya-yuklash
mkdir -p "$B"
rm -f "$B/tayyor" "$B/xato"
: > "$B/jurnal"
yoz() { echo "$(date '+%F %T') $*" >> "$B/jurnal"; }
tamom() { echo "$2" > "$B/$1"; yoz "$1: $2"; exit 0; }

[ -d "$YANGI" ] || tamom xato "yangi versiya ($YANGI) yo'q"
[ -f "$YANGI/ornatish/.env" ] || tamom xato "ornatish/.env (MIYA_DOMEN) yo'q"

compose() { docker compose -p miya --env-file "$JORIY/ornatish/.env" -f "$JORIY/ornatish/docker-compose.server.yml" "$@"; }
sogmi() {
  local h=""
  for _ in $(seq 60); do
    h=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' miya 2>/dev/null)
    [ "$h" = healthy ] && return 0
    sleep 2
  done
  [ -n "$h" ] || h="aniqlanmadi"
  yoz "sog'lik holati: $h"
  return 1
}

# boshlang'ich ma'lumot — faqat hajm bo'sh bo'lsa (server ma'lumotini hech qachon ustidan yozmaydi)
if [ -f "$B/boshlangich/miya.db" ]; then
  docker volume inspect miya_malumot >/dev/null 2>&1 || docker volume create miya_malumot >/dev/null
  V=$(docker volume inspect miya_malumot -f '{{.Mountpoint}}')
  if [ -f "$V/miya.db" ]; then
    yoz "hajmda baza bor — boshlang'ich ma'lumot KO'CHIRILMADI"
  else
    cp "$B/boshlangich/miya.db" "$V/miya.db"
    [ -f "$B/boshlangich/.kalit" ] && cp "$B/boshlangich/.kalit" "$V/.kalit" && chmod 600 "$V/.kalit"
    chown -R 10003 "$V"
    yoz "boshlang'ich baza hajmga ko'chirildi"
  fi
  rm -rf "$B/boshlangich"
fi

rm -rf "$ESKI"
[ -d "$JORIY" ] && mv "$JORIY" "$ESKI"
mv "$YANGI" "$JORIY"
yoz "yangi versiya joyida; yig'ilmoqda"

if compose up -d --build >> "$B/jurnal" 2>&1 && sogmi; then
  install -m 755 "$JORIY/ornatish/miya-caddy-qorovul" /usr/local/sbin/miya-caddy-qorovul
  install -m 755 "$JORIY/ornatish/miya-zaxira" /usr/local/sbin/miya-zaxira
  install -m 644 "$JORIY"/ornatish/systemd/miya-*.service "$JORIY"/ornatish/systemd/miya-*.timer /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now miya-caddy-qorovul.timer miya-zaxira.timer >> "$B/jurnal" 2>&1
  /usr/local/sbin/miya-caddy-qorovul
  tamom tayyor "ishlayapti"
fi

yoz "yangi versiya ishga tushmadi — qaytarilmoqda"
docker logs --tail 40 miya >> "$B/jurnal" 2>&1
if [ -d "$ESKI" ]; then
  rm -rf "$JORIY.xato"
  mv "$JORIY" "$JORIY.xato"
  mv "$ESKI" "$JORIY"
  if compose up -d --build >> "$B/jurnal" 2>&1 && sogmi; then
    tamom xato "yangi versiya ishga tushmadi; eski versiya tiklandi (xatoli nusxa: $JORIY.xato)"
  fi
  tamom xato "yangi versiya ham, eski versiya ham ishga tushmadi — jurnalni ko'ring"
fi
compose down >> "$B/jurnal" 2>&1
tamom xato "birinchi o'rnatish ishga tushmadi — jurnalni ko'ring"
