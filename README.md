# DoorDrop

A small screen by the front door that shows the delivery code, so the phone stays in the other room.

Bangalore runs on one-time passwords. Every delivery — food, groceries, a parcel — ends with someone at the door waiting while you find your phone, unlock it, open Messages, read four digits, and lock it again. The four digits take a second. Everything around them costs about twenty minutes, because the phone you unlocked had other plans for you.

So: put the four digits somewhere else.

## How it works

```
iPhone ──SMS──▶ Text Message Forwarding ──▶ ~/Library/Messages/chat.db
                                                      │
                                           agent/otp_watcher.py
                                           (5s poll, ROWID cursor)
                                                      │
                                              HTTPS + bearer
                                                      ▼
                                            api/otp/latest.ts
                                            (Vercel Edge + Edge Config)
                                                      │
                                              HTTP GET, every 10s
                                                      ▼
                                          ESP32 ──I²C──▶ SSD1306
```

A Mac already has every SMS the phone receives, sitting in a SQLite database, if Text Message Forwarding is on. No SMS gateway, no Twilio number, no carrier integration. The watcher tails that database from a high-water ROWID, decides whether a message carries a code worth showing, and pushes it to an endpoint the ESP32 polls.

The ESP32 pulls rather than being pushed to, because a device on a home network behind NAT has no stable address, and giving it one is a bigger project than the problem deserves.

**Hardware.** ESP32-WROOM-32, a 0.96" 128×64 SSD1306 over I²C, three jumpers. VCC→3V3, GND→GND, SCL→GPIO22, SDA→GPIO21, address `0x3C`. Under fifteen dollars.

## State: the firmware has never run

I want to be exact about this, because "IoT project" usually implies a photograph of a working device and there isn't one.

The software pipeline is real. The watcher, the API, and the extraction logic work and were exercised. The firmware was written and never flashed. The Arduino IDE logs on my machine show the board connected on a CP2102 bridge at 14:33 on 2026-04-27 and disconnected at 15:20 — but `Adafruit_GFX`, `Adafruit_SSD1306`, and `ArduinoJson` were never installed, the sketch never appears in a build log, and no compile or upload was ever attempted. Forty-seven minutes with the board plugged in, and I spent them on the parts that were not the hard part.

`firmware/doordrop/doordrop.ino` is 114 lines of unverified C++. It polls, parses JSON, change-detects, and centres the code at text size 3 using `getTextBounds`. It compiles in my head. That is not a claim about hardware.

The deployed endpoint is also down — the Vercel account is disabled, so `doordrop-otp.vercel.app` returns 402. Run it locally.

## What I got wrong

Rebuilding the extractor for this repository turned up three bugs, and one of them mattered.

**The screen would have shown your bank codes.** The original filter was `WATCH_HANDLES = []`, which means accept everything, combined with a regex that took the first four-to-eight digit run in any message. A device whose entire purpose is to display codes to whoever is standing at the door would have displayed HDFC's one-time password, WhatsApp's login code, and Google's 2FA, to the same audience. The threat model was inverted: I built a thing to save myself twenty minutes and pointed it at my authentication factors.

`agent/extract.py` now requires a cue word (`OTP`, `code`, `PIN`) adjacent to the digits, defaults to an allow-list of delivery senders, and enforces a deny-list for financial and account messages that `delivery_only=False` cannot switch off.

```python
def test_never_displays_financial_or_account_codes(text, handle):
    # These are exactly the messages the first version would have shown,
    # to whoever was standing at the door.
    r = extract(text, handle, delivery_only=False)
    assert r.code is None
```

**It showed order numbers.** `\b(\d{4,8})\b` against "Your Amazon order 1140377 is arriving today" yields 1140377. There is no code in that message at all. The extractor now needs a cue word and rejects digits sitting next to _order_, _tracking_, _invoice_, _amount_.

**Codes never expired.** A timestamp was written into the payload and never read, so a code from three hours ago stayed on the screen until something replaced it. Codes now carry `expires_at`.

The logs changed too. This runs on a machine that sees every SMS the phone receives, so the watcher logs its _decision_ and never the message — and the refusal path deliberately does not log the code it refused.

## Running it

```bash
# the extractor's tests need no hardware and no database
cd agent && python3 -m pytest        # 30 tests

# the watcher, once Text Message Forwarding is on
cp .env.example .env                 # DOORDROP_API, OTP_TOKEN
python3 otp_watcher.py
```

`docs/FLASH.md` covers the board side. Grant the terminal Full Disk Access first or the Messages store is unreadable.

## The argument

The landing page for this had a calculator on it: how long a phone interruption actually costs once you count the tail, against how long looking at four digits takes. That ratio is the whole product. The screen is not convenient — walking to the door is not faster than looking at your phone. It is _narrower_. It can show you a delivery code and it cannot show you anything else, and the second half is the point.

Which is why the bug above was the one that mattered. A device that can show you your bank code is no longer narrow. It is just a worse phone, mounted to a wall.

## License

MIT.
