# Flashing the board

## Parts

| Part | Notes |
| --- | --- |
| ESP32-WROOM-32 dev board | any CP2102 or CH340 variant |
| 0.96" SSD1306 OLED, 128×64, I²C | the 4-pin kind, not the 7-pin SPI kind |
| 3 jumper wires | female-to-female if both boards have pins |

## Wiring

| OLED | ESP32 |
| --- | --- |
| VCC | 3V3 — not 5V |
| GND | GND |
| SCL | GPIO22 |
| SDA | GPIO21 |

I²C address is `0x3C`. If the screen stays dark, try `0x3D` — the two are
common and the silkscreen rarely says which you have.

## Arduino IDE setup

1. Boards Manager → install **esp32** by Espressif.
2. Library Manager → install **Adafruit GFX**, **Adafruit SSD1306**, **ArduinoJson**.
3. Board: *ESP32 Dev Module*. Flash 4MB (QIO), CPU 240MHz, upload 921600.
4. Port: `/dev/cu.usbserial-*` (CP2102) or `/dev/cu.wchusbserial-*` (CH340).
   No port means a missing USB-UART driver, not a dead board.

## Configure

Set three constants at the top of `firmware/doordrop/doordrop.ino`:

```cpp
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* OTP_TOKEN     = "YOUR_OTP_TOKEN";   // must match the server's
```

`OTP_TOKEN` is a shared secret you generate — `openssl rand -hex 24` — and
set in both places: here, and as the `OTP_TOKEN` environment variable on
the API. Anyone holding it can write to your display.

Set `OTP_URL` to wherever you deployed the API, or your machine's LAN
address while developing.

## Verify

Serial monitor at 115200 should show the WiFi join, then one poll line
every 10 seconds. If polls return 401, the tokens do not match. If they
return 200 with an empty body, the watcher has not pushed anything yet —
send yourself a test message shaped like `Swiggy OTP is 4821`.

> **Never flashed.** This procedure is written from the datasheets and
> the pin assignments in the sketch, not from a board that has run it.
> See the README.
