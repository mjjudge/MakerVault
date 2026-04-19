"""Part intake service — normalisation, candidate matching, code generation,
and storage suggestion.

All logic is pure-Python with no AI provider dependency so the intake
workflow is available even when no AI provider is configured.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Known family lookup — substring match on lowercased description.
# Checked in order; first match wins.
# Format: (search_string, category, subcategory, family)
# ---------------------------------------------------------------------------

_KNOWN_FAMILIES: list[tuple[str, str, str, str]] = [
    # MCU / dev boards — check specific families before generic keywords
    ("raspberry pi pico", "MCU", "DEV", "RPIPICO"),
    ("rp2040", "MCU", "DEV", "RP2040"),
    ("esp32-s3", "MCU", "DEV", "ESP32S3"),
    ("esp32-s2", "MCU", "DEV", "ESP32S2"),
    ("esp32-c3", "MCU", "DEV", "ESP32C3"),
    ("esp32", "MCU", "DEV", "ESP32"),
    ("esp8266", "MCU", "DEV", "ESP8266"),
    ("esp-12", "MCU", "DEV", "ESP8266"),
    ("stm32", "MCU", "DEV", "STM32"),
    ("arduino", "MCU", "DEV", "ARDUINO"),
    ("teensy", "MCU", "DEV", "TEENSY"),
    ("attiny", "MCU", "DEV", "ATTINY"),
    ("atmega", "MCU", "DEV", "ATMEGA"),
    ("samd21", "MCU", "DEV", "SAMD21"),
    ("bluepill", "MCU", "DEV", "STM32"),
    # Sensors — IMU
    ("mpu-6050", "SEN", "IMU", "MPU6050"),
    ("mpu6050", "SEN", "IMU", "MPU6050"),
    ("mpu 6050", "SEN", "IMU", "MPU6050"),
    ("gy-521", "SEN", "IMU", "MPU6050"),
    ("gy521", "SEN", "IMU", "MPU6050"),
    ("icm-20948", "SEN", "IMU", "ICM20948"),
    ("bno055", "SEN", "IMU", "BNO055"),
    ("lsm6ds", "SEN", "IMU", "LSM6DS"),
    ("adxl345", "SEN", "IMU", "ADXL345"),
    # Sensors — environment
    ("bme680", "SEN", "ENV", "BME680"),
    ("bme280", "SEN", "ENV", "BME280"),
    ("dht22", "SEN", "ENV", "DHT22"),
    ("dht11", "SEN", "ENV", "DHT11"),
    ("aht20", "SEN", "ENV", "AHT20"),
    ("sht31", "SEN", "ENV", "SHT31"),
    ("htu21", "SEN", "ENV", "HTU21"),
    ("sht30", "SEN", "ENV", "SHT30"),
    # Sensors — pressure
    ("bmp280", "SEN", "PRS", "BMP280"),
    ("bmp180", "SEN", "PRS", "BMP180"),
    ("bmp085", "SEN", "PRS", "BMP085"),
    # Sensors — temperature
    ("ds18b20", "SEN", "TMP", "DS18B20"),
    ("max6675", "SEN", "TMP", "MAX6675"),
    # Sensors — distance
    ("hc-sr04", "SEN", "DIS", "HCSR04"),
    ("hcsr04", "SEN", "DIS", "HCSR04"),
    ("vl53l1", "SEN", "DIS", "VL53L1"),
    ("vl53l0", "SEN", "DIS", "VL53L0"),
    ("tf-luna", "SEN", "DIS", "TFLUNA"),
    # Sensors — motion / PIR
    ("hc-sr501", "SEN", "MOT", "HCSR501"),
    ("hcsr501", "SEN", "MOT", "HCSR501"),
    # Sensors — gas / air quality
    ("mq-135", "SEN", "GAS", "MQ135"),
    ("mq135", "SEN", "GAS", "MQ135"),
    ("mq-2", "SEN", "GAS", "MQ2"),
    ("mq2", "SEN", "GAS", "MQ2"),
    ("mq-7", "SEN", "GAS", "MQ7"),
    ("mq7", "SEN", "GAS", "MQ7"),
    ("ccs811", "SEN", "GAS", "CCS811"),
    ("sgp30", "SEN", "GAS", "SGP30"),
    # Sensors — light
    ("bh1750", "SEN", "LUX", "BH1750"),
    ("tsl2591", "SEN", "LUX", "TSL2591"),
    ("veml6070", "SEN", "LUX", "VEML6070"),
    # Sensors — biometric
    ("max30102", "SEN", "BIO", "MAX30102"),
    ("max30100", "SEN", "BIO", "MAX30100"),
    # Sensors — weight
    ("hx711", "SEN", "WGT", "HX711"),
    # Power
    ("tp4056", "PWR", "CHG", "TP4056"),
    ("tp5100", "PWR", "CHG", "TP5100"),
    ("ams1117", "PWR", "REG", "AMS1117"),
    ("lm7805", "PWR", "REG", "LM7805"),
    ("lm317", "PWR", "REG", "LM317"),
    ("xl4016", "PWR", "CNV", "XL4016"),
    ("mp1584", "PWR", "CNV", "MP1584"),
    ("mt3608", "PWR", "CNV", "MT3608"),
    ("xl6009", "PWR", "CNV", "XL6009"),
    ("ina219", "PWR", "MON", "INA219"),
    ("ina3221", "PWR", "MON", "INA3221"),
    # Communications
    ("nrf24l01", "COM", "RF", "NRF24L01"),
    ("nrf24", "COM", "RF", "NRF24L01"),
    ("max485", "COM", "RS4", "MAX485"),
    ("hc-05", "COM", "BLE", "HC05"),
    ("hc-06", "COM", "BLE", "HC06"),
    ("hc05", "COM", "BLE", "HC05"),
    ("hc06", "COM", "BLE", "HC06"),
    ("sim800", "COM", "GSM", "SIM800"),
    ("sim900", "COM", "GSM", "SIM900"),
    ("ra-02", "COM", "LOR", "RA02"),
    ("sx1276", "COM", "LOR", "SX1276"),
    ("mfrc522", "COM", "NFC", "MFRC522"),
    ("pn532", "COM", "NFC", "PN532"),
    ("w5500", "COM", "ETH", "W5500"),
    ("enc28j60", "COM", "ETH", "ENC28J60"),
    # Drivers
    ("l298n", "DRV", "MOT", "L298N"),
    ("l293d", "DRV", "MOT", "L293D"),
    ("a4988", "DRV", "MOT", "A4988"),
    ("drv8825", "DRV", "MOT", "DRV8825"),
    ("tb6600", "DRV", "MOT", "TB6600"),
    ("drv8833", "DRV", "MOT", "DRV8833"),
    # Display
    ("ssd1306", "DIS", "OLE", "SSD1306"),
    ("sh1106", "DIS", "OLE", "SH1106"),
    ("ili9341", "DIS", "LCD", "ILI9341"),
    ("st7789", "DIS", "LCD", "ST7789"),
    ("st7735", "DIS", "LCD", "ST7735"),
    ("max7219", "DIS", "SEG", "MAX7219"),
    ("tm1637", "DIS", "SEG", "TM1637"),
    # Connectors — specific breakout boards (check before generic USB keywords)
    ("micro usb breakout", "CON", "USB", "USBMICRO"),
    ("microusb breakout", "CON", "USB", "USBMICRO"),
    ("usb-c breakout", "CON", "USB", "USBC"),
    ("usb c breakout", "CON", "USB", "USBC"),
    ("mini usb breakout", "CON", "USB", "USBMINI"),
]

# ---------------------------------------------------------------------------
# Keyword classification rules
# Format: (positive_keywords, negative_keywords, category, subcategory)
# Checked in order; first rule where all positive keywords match and no
# negative keyword matches wins.
# ---------------------------------------------------------------------------

# MCU family tokens — at least one must appear for "board"/"module" to become MCU
_MCU_FAMILY_TOKENS: frozenset[str] = frozenset({
    "esp32", "esp8266", "esp-12", "esp12", "esp-32", "esp-8266",
    "stm32", "rp2040", "raspberry pi pico",
    "arduino", "teensy", "attiny", "atmega",
    "samd21", "samd51", "nrf52", "bluepill",
})

_KEYWORD_RULES: list[tuple[set[str], set[str], str, str]] = [
    # MCU — explicit MCU vocabulary (no family lookup needed)
    ({"microcontroller", "mcu", "microprocessor"}, set(), "MCU", "DEV"),
    ({"dev board", "devkit", "development board", "dev kit"}, set(), "MCU", "DEV"),
    # Sensors — specific subtypes first, generic "sensor" last
    ({"accelerometer", "gyroscope", "imu", "gyro", "inertial measurement"}, set(), "SEN", "IMU"),
    ({"thermocouple", "thermistor"}, set(), "SEN", "TMP"),
    ({"temperature", "humidity"}, set(), "SEN", "ENV"),
    ({"barometric", "barometer", "altimeter"}, set(), "SEN", "PRS"),
    ({"ultrasonic", "distance sensor", "ranging sensor", "time-of-flight", "tof sensor", "lidar"}, set(), "SEN", "DIS"),
    ({"pir", "passive infrared", "motion sensor", "mmwave", "radar module"}, set(), "SEN", "MOT"),
    ({"gas sensor", "smoke sensor", "air quality", "co2 sensor", "voc sensor"}, set(), "SEN", "GAS"),
    ({"light sensor", "ldr", "photodiode", "colour sensor", "color sensor", "uv sensor", "ambient light"}, set(), "SEN", "LUX"),
    ({"microphone module", "sound sensor", "audio sensor"}, set(), "SEN", "SND"),
    ({"hall effect", "reed switch", "magnetic sensor", "position sensor"}, set(), "SEN", "POS"),
    ({"load cell", "weight sensor", "strain gauge"}, set(), "SEN", "WGT"),
    ({"touch sensor", "capacitive sensor"}, set(), "SEN", "TCH"),
    ({"gps module", "gnss module", "gps receiver"}, set(), "SEN", "GPS"),
    ({"camera module", "ov2640", "ov7670"}, set(), "SEN", "CAM"),
    ({"rtc module", "real time clock", "real-time clock"}, set(), "SEN", "RTC"),
    ({"sensor"}, set(), "SEN", "GEN"),
    # Communications
    ({"wifi module", "wi-fi module", "wireless module"}, set(), "COM", "WIF"),
    ({"bluetooth module", "ble module"}, set(), "COM", "BLE"),
    ({"zigbee"}, set(), "COM", "ZIG"),
    ({"lora module", "lorawan"}, set(), "COM", "LOR"),
    ({"gsm module", "gprs module", "4g module", "cellular module"}, set(), "COM", "GSM"),
    ({"nfc module", "rfid module", "rfid reader"}, set(), "COM", "NFC"),
    ({"can bus", "canbus"}, set(), "COM", "CAN"),
    ({"rs-485 module", "rs485 module", "modbus module"}, set(), "COM", "RS4"),
    ({"ethernet module"}, set(), "COM", "ETH"),
    # Power — chargers before generic "battery" rules
    ({"lipo charger", "battery charger", "usb charger", "charging module"}, set(), "PWR", "CHG"),
    ({"buck converter", "boost converter", "step-down converter", "step down converter",
      "step-up converter", "step up converter", "dc-dc converter"}, set(), "PWR", "CNV"),
    ({"voltage regulator", "ldo regulator", "linear regulator"}, set(), "PWR", "REG"),
    ({"current sensor", "power monitor", "voltage monitor", "energy monitor"}, set(), "PWR", "MON"),
    ({"ups module", "uninterruptible power"}, set(), "PWR", "UPS"),
    ({"battery holder", "battery pack", "lipo battery", "lithium battery", "battery shield"}, set(), "PWR", "BAT"),
    ({"power supply module", "psu module"}, set(), "PWR", "PSU"),
    # Actuators
    ({"relay module", "relay board"}, set(), "ACT", "REL"),
    ({"servo motor", "servo module"}, set(), "ACT", "SRV"),
    ({"stepper motor", "dc motor", "brushless motor"}, set(), "ACT", "MOT"),
    ({"solenoid"}, set(), "ACT", "SOL"),
    ({"buzzer module", "piezo buzzer"}, set(), "ACT", "BUZ"),
    # Drivers
    ({"motor driver", "motor controller", "h-bridge"}, set(), "DRV", "MOT"),
    ({"led driver", "ws2812", "ws2811", "neopixel", "rgb driver"}, set(), "DRV", "LED"),
    # Display
    ({"oled display", "oled module", "oled screen"}, set(), "DIS", "OLE"),
    ({"lcd display", "lcd module", "tft display", "tft screen", "tft module"}, set(), "DIS", "LCD"),
    ({"e-paper", "epaper", "e-ink", "eink"}, set(), "DIS", "EPD"),
    ({"7-segment", "seven segment", "digit display", "7 segment"}, set(), "DIS", "SEG"),
    ({"display module", "display board", "display screen"}, set(), "DIS", "GEN"),
    # Connectors / Interface — USB variants before generic breakout
    ({"micro usb", "micro-usb", "microusb"}, set(), "CON", "USB"),
    ({"mini usb", "mini-usb", "miniusb"}, set(), "CON", "USB"),
    ({"usb-c connector", "usb-c breakout", "usb c breakout",
      "type-c breakout", "type c breakout"}, set(), "CON", "USB"),
    ({"usb connector", "usb socket", "usb breakout", "usb adapter board",
      "usb female", "usb port"}, set(), "CON", "USB"),
    ({"level shifter", "level converter", "logic level converter"}, set(), "CON", "LVL"),
    ({"i2c hub", "i2c multiplexer", "i2c expander"}, set(), "CON", "I2C"),
    ({"breakout board", "breakout module", "pin breakout", "adapter board"}, set(), "CON", "BRK"),
    # Passive — discrete components
    ({"resistor", "resistance"}, set(), "PAS", "RES"),
    ({"capacitor", "capacitance"}, set(), "PAS", "CAP"),
    ({"inductor", "inductance", "choke", "ferrite bead"}, set(), "PAS", "IND"),
    ({"crystal oscillator", "xtal", "crystal resonator"}, set(), "PAS", "XTL"),
    ({"potentiometer", "trimpot", "trim pot", "variable resistor"}, set(), "PAS", "TRM"),
    ({"diode", "schottky diode", "zener diode"}, set(), "PAS", "DIO"),
    ({"transistor", "mosfet", "bjt", "jfet"}, set(), "PAS", "TRS"),
    ({"led", "light emitting diode"}, set(), "DIS", "LED"),
    # Switches / Input
    ({"joystick"}, set(), "SWI", "JOY"),
    ({"keypad", "matrix keyboard"}, set(), "SWI", "KEY"),
    ({"dip switch"}, set(), "SWI", "DIP"),
    ({"toggle switch"}, set(), "SWI", "TOG"),
    ({"pushbutton", "push button", "tactile switch", "momentary switch"}, set(), "SWI", "BTN"),
    ({"rotary encoder"}, set(), "SWI", "ENC"),
    # Mechanical
    ({"enclosure", "project box", "project case"}, set(), "MEC", "BOX"),
    ({"heatsink", "heat sink"}, set(), "MEC", "HSK"),
    ({"standoff", "pcb spacer", "pcb mount"}, set(), "MEC", "MNT"),
    # Cables
    ({"usb cable"}, set(), "CAB", "USB"),
    ({"jumper wire", "dupont wire"}, set(), "CAB", "JMP"),
    ({"jst cable"}, set(), "CAB", "JST"),
    ({"ribbon cable"}, set(), "CAB", "RIB"),
    ({"cable", "wire"}, set(), "CAB", "GEN"),
    # Tools
    ({"programmer", "usbasp", "st-link", "j-link", "jtag", "swd adapter"}, set(), "TOO", "PRG"),
    ({"logic analyzer", "oscilloscope"}, set(), "TOO", "TST"),
    ({"tool"}, set(), "TOO", "GEN"),
    # Generic module/board — lowest priority, only when nothing else matched
    ({"module", "board"}, set(), "MOD", "GEN"),
]

# Common stop words to strip from tokens
_STOP_WORDS = frozenset(
    {
        "a", "an", "the", "of", "for", "and", "or", "in", "on", "at", "to",
        "with", "by", "as", "is", "it", "be", "this", "that", "some", "piece",
        "type", "pack", "pcs", "pce", "lot", "set", "each", "unit", "units",
    }
)

# Package designator patterns  (normalise common variants)
_PACKAGE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b0201\b", re.I), "0201"),
    (re.compile(r"\b0402\b", re.I), "0402"),
    (re.compile(r"\b0603\b", re.I), "0603"),
    (re.compile(r"\b0805\b", re.I), "0805"),
    (re.compile(r"\b1206\b", re.I), "1206"),
    (re.compile(r"\b1210\b", re.I), "1210"),
    (re.compile(r"\bsmd\b", re.I), "SMD"),
    (re.compile(r"\bsmt\b", re.I), "SMD"),
    (re.compile(r"\bthrou?gh.?hole\b", re.I), "THT"),
    (re.compile(r"\btht\b", re.I), "THT"),
    (re.compile(r"\bsot.?23\b", re.I), "SOT23"),
    (re.compile(r"\bsot.?223\b", re.I), "SOT223"),
    (re.compile(r"\bto.?92\b", re.I), "TO92"),
    (re.compile(r"\bto.?220\b", re.I), "TO220"),
    (re.compile(r"\bdip\b", re.I), "DIP"),
    (re.compile(r"\bsoic\b", re.I), "SOIC"),
    (re.compile(r"\bqfp\b", re.I), "QFP"),
    (re.compile(r"\bqfn\b", re.I), "QFN"),
    (re.compile(r"\bbga\b", re.I), "BGA"),
]

# Value patterns:  10k, 100nF, 3.3V, 1uH, etc.
# Uses \s? (optional single space) instead of \s* to avoid polynomial ReDoS
# on pathological inputs with many repeated spaces.
_VALUE_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s?(k|M|G|m|u|µ|n|p)?\s?(ohm|ohms|Ω|F|H|V|A|W|hz|Hz)\b"
    r"|\b(\d+(?:\.\d+)?)\s?(k|M|G)?\s?(r|R|ohm|ohms)\b"
    r"|\b(\d+(?:\.\d+)?)\s?(k|K)\b"
    r"|\b(\d+(?:\.\d+)?)\s?(m|u|µ|n|p)(F|H)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Internal classification helper
# ---------------------------------------------------------------------------


def _kw_matches(kw: str, lower: str, token_set: set[str]) -> bool:
    """Return True if *kw* matches *lower*.

    Multi-word keywords (containing a space) use substring matching — a space
    can't hide inside another token so false positives are impossible.
    Single-word keywords use token-set membership so that e.g. "mcu" does NOT
    match "cjmcu", "imu" does not match "simulator", etc.
    """
    if " " in kw:
        return kw in lower
    return kw in token_set


def _classify(lower: str, token_set: set[str]) -> tuple[str | None, str | None, str | None]:
    """Classify a lowercased description → (category, subcategory, family).

    Priority:
    1. Known family match (exact substring in order).
    2. Keyword rules (positive match, no negative hit; MCU requires explicit
       MCU family token to prevent "board"/"module" from becoming MCU).
    3. (None, None, None) — caller applies the UNK fallback.
    """
    # Step 1: known family — these are specific enough that substring is safe
    for pattern, cat, sub, fam in _KNOWN_FAMILIES:
        if pattern in lower:
            return cat, sub, fam

    # Step 2: keyword rules — single-word keywords match whole tokens only
    for pos_kw, neg_kw, cat, sub in _KEYWORD_RULES:
        if not any(_kw_matches(kw, lower, token_set) for kw in pos_kw):
            continue
        if neg_kw and any(_kw_matches(nk, lower, token_set) for nk in neg_kw):
            continue
        # MCU rule: require either an explicit MCU family token (esp32, arduino,
        # etc.) OR the words "microcontroller"/"mcu"/"microprocessor" as whole
        # tokens — "cjmcu" must not satisfy this.
        if cat == "MCU" and sub == "DEV":
            has_mcu_family = any(fam_tok in lower for fam_tok in _MCU_FAMILY_TOKENS)
            has_mcu_explicit = any(kw in token_set for kw in (
                "microcontroller", "mcu", "microprocessor"
            ))
            if not has_mcu_family and not has_mcu_explicit:
                continue
        return cat, sub, None

    return None, None, None


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


@dataclass
class NormalisedDescription:
    """Result of normalising a free-text part description."""

    raw: str
    tokens: list[str]
    package_hint: str | None = None
    value_hints: list[str] = field(default_factory=list)
    kind_prefix: str | None = None   # CAT-SUB  e.g. "PAS-RES", "SEN-IMU"
    family: str | None = None         # e.g. "MPU6050", "USBMICRO"


def normalise_description(description: str) -> NormalisedDescription:
    """Normalise *description* to a structured representation.

    Steps:
    1. Lowercase and strip.
    2. Extract package designators.
    3. Extract value hints (e.g. "10k", "100nF").
    4. Tokenise (split on whitespace and punctuation).
    5. Remove stop words.
    6. Classify using family lookup then keyword rules.
    """
    text = description.strip()

    # --- Package extraction -------------------------------------------------
    package_hint: str | None = None
    for pattern, canonical in _PACKAGE_PATTERNS:
        if pattern.search(text):
            package_hint = canonical
            break

    # --- Value extraction ---------------------------------------------------
    value_hints = [m.group(0) for m in _VALUE_RE.finditer(text)]

    # --- Tokenise -----------------------------------------------------------
    lower = text.lower()
    cleaned = re.sub(r"[^\w\s-]", " ", lower)
    raw_tokens = cleaned.split()
    tokens = [t for t in raw_tokens if t and t not in _STOP_WORDS and len(t) > 1]

    # --- Classify -----------------------------------------------------------
    token_set = set(tokens)
    cat, sub, fam = _classify(lower, token_set)

    kind_prefix: str | None = None
    if cat and sub:
        kind_prefix = f"{cat}-{sub}"

    return NormalisedDescription(
        raw=description,
        tokens=tokens,
        package_hint=package_hint,
        value_hints=value_hints,
        kind_prefix=kind_prefix,
        family=fam,
    )


# ---------------------------------------------------------------------------
# Candidate scoring helpers
# ---------------------------------------------------------------------------


def _token_set(text: str | None) -> set[str]:
    """Tokenise *text* into a lowercase word set (for overlap scoring)."""
    if not text:
        return set()
    lower = text.lower()
    cleaned = re.sub(r"[^\w\s-]", " ", lower)
    return {t for t in cleaned.split() if t and len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _substring_score(haystack: str | None, needle: str) -> int:
    """Return 30 if *needle* is a substring of *haystack* (case-insensitive)."""
    if not haystack or not needle:
        return 0
    return 30 if needle.lower() in haystack.lower() else 0


def score_candidate(
    part_name: str,
    part_aliases: list[str] | None,
    part_mpn: str | None,
    part_short_desc: str | None,
    normed: NormalisedDescription,
) -> int:
    """Compute a 0–100 confidence score for one candidate part.

    Scoring components (sum, capped at 100):
    - Jaccard overlap between description tokens and part-name tokens: 0–50
      OR query-coverage score (fraction of query tokens found in part): 0–35
      (whichever is higher — ensures short queries like "breadboard" match well)
    - Exact package match (package_hint in part tokens): +15
    - MPN substring match: +20
    - Alias token overlap bonus: +15
    """
    query_tokens = set(normed.tokens)

    # Name/description overlap
    name_tokens = _token_set(part_name) | _token_set(part_short_desc)
    alias_tokens: set[str] = set()
    for alias in (part_aliases or []):
        alias_tokens |= _token_set(alias)
    all_part_tokens = name_tokens | alias_tokens

    jaccard = _jaccard(query_tokens, all_part_tokens)
    jaccard_score = int(jaccard * 50)

    # Coverage score: how much of the query is covered by the part tokens?
    # This rescues short queries (e.g. "breadboard") that score low on Jaccard
    # because the part name has many unrelated tokens.
    coverage = (
        len(query_tokens & all_part_tokens) / len(query_tokens)
        if query_tokens else 0.0
    )
    coverage_score = int(coverage * 35)

    base = max(jaccard_score, coverage_score)

    # Package hint bonus
    package_bonus = 0
    if normed.package_hint:
        if normed.package_hint.lower() in all_part_tokens:
            package_bonus = 15

    # MPN substring match
    mpn_bonus = 0
    if part_mpn:
        mpn_tokens = _token_set(part_mpn)
        if query_tokens & mpn_tokens:
            mpn_bonus = 20

    # Alias bonus
    alias_bonus = 0
    if alias_tokens:
        alias_jaccard = _jaccard(query_tokens, alias_tokens)
        alias_bonus = int(alias_jaccard * 15)

    return min(100, base + package_bonus + mpn_bonus + alias_bonus)


# ---------------------------------------------------------------------------
# Code generation
# ---------------------------------------------------------------------------

# Separator character for generated codes
_SEP = "-"


def _build_code_prefix(normed: NormalisedDescription) -> str:
    """Build the CAT-SUB-FAMILY prefix for the generated code.

    Examples:
      "10k resistor 0603"        → "PAS-RES-10K-0603"
      "ESP32 dev board"          → "MCU-DEV-ESP32"
      "MPU-6050 IMU"             → "SEN-IMU-MPU6050"
      "Micro USB breakout board" → "CON-USB-USBMICRO"
      "unknown widget"           → "UNK-GEN-GENERIC"
    """
    parts: list[str] = []

    if normed.kind_prefix:
        parts.append(normed.kind_prefix)

    # Family from lookup takes priority over value hints
    if normed.family:
        parts.append(normed.family)
    elif normed.value_hints:
        val = re.sub(r"\s+", "", normed.value_hints[0]).upper()
        parts.append(val)

    # Add package hint (relevant for passive components)
    if normed.package_hint:
        parts.append(normed.package_hint)

    # If we have no family/value yet, add the most descriptive token
    if len(parts) <= 1:
        existing_lower = {p.lower() for p in parts}
        for tok in normed.tokens:
            if tok.lower() not in existing_lower and not tok.isdigit() and len(tok) > 2:
                if tok.lower() not in _STOP_WORDS:
                    parts.append(tok.upper())
                    break

    if not parts:
        # Fallback: take up to 3 tokens from the description
        parts = [t.upper() for t in normed.tokens[:3]]

    return _SEP.join(parts) if parts else "UNK-GEN-GENERIC"


async def suggest_part_code(description: str, db: AsyncSession) -> str:
    """Generate a unique, human-readable part code from *description*.

    The generated code has the form:  ``PREFIX-NNN``  where PREFIX is derived
    from the description and NNN is a zero-padded sequence number that makes
    the code unique within the current database.

    E.g.  "10k resistor 0603"        →  "PAS-RES-10K-0603-001"
          "MPU-6050 IMU breakout"    →  "SEN-IMU-MPU6050-001"
          "Micro USB breakout board" →  "CON-USB-USBMICRO-001"
    """
    from makervault.models.part import Part

    normed = normalise_description(description)
    prefix = _build_code_prefix(normed)

    # Find all existing codes with this prefix to determine the next sequence
    result = await db.execute(
        select(Part.part_code).where(
            Part.part_code.like(f"{prefix}{_SEP}%")
        )
    )
    existing_codes = {row[0] for row in result.all()}

    # Also check if the prefix itself exists as a code
    check = await db.execute(
        select(Part.part_code).where(Part.part_code == prefix)
    )
    if check.scalar_one_or_none() is not None:
        existing_codes.add(prefix)

    # Find lowest available sequence number
    seq = 1
    while True:
        candidate = f"{prefix}{_SEP}{seq:03d}"
        if candidate not in existing_codes:
            return candidate
        seq += 1


# ---------------------------------------------------------------------------
# Candidate matching
# ---------------------------------------------------------------------------

_MIN_CONFIDENCE = 8  # Candidates below this score are excluded


async def find_candidates(
    description: str,
    db: AsyncSession,
    limit: int = 5,
    category_id: uuid.UUID | None = None,
) -> list[dict]:
    """Load active parts from *db* and return ranked match candidates.

    Each candidate dict has keys: ``part_id``, ``part_code``, ``name``,
    ``short_description``, ``manufacturer``, ``manufacturer_part_number``,
    ``part_kind``, ``confidence``, ``match_reason``.
    """
    from makervault.models.part import Part

    normed = normalise_description(description)

    query = select(Part).where(Part.is_active.is_(True))
    if category_id is not None:
        query = query.where(Part.category_id == category_id)

    result = await db.execute(query.order_by(Part.name))
    parts = result.scalars().all()

    scored: list[tuple[int, dict]] = []
    for p in parts:
        aliases = list(p.aliases) if p.aliases else []
        confidence = score_candidate(
            part_name=p.name,
            part_aliases=aliases,
            part_mpn=p.manufacturer_part_number,
            part_short_desc=p.short_description,
            normed=normed,
        )
        if confidence < _MIN_CONFIDENCE:
            continue

        # Build a human-readable match reason
        reasons: list[str] = []
        name_tokens = _token_set(p.name)
        overlap = set(normed.tokens) & name_tokens
        if overlap:
            reasons.append(f"name matches: {', '.join(sorted(overlap))}")
        if normed.package_hint and normed.package_hint.lower() in _token_set(p.name) | {
            a.lower() for a in aliases
        }:
            reasons.append(f"package match ({normed.package_hint})")
        if p.manufacturer_part_number and any(
            t in p.manufacturer_part_number.lower() for t in normed.tokens
        ):
            reasons.append("MPN match")
        if not reasons:
            reasons.append("partial keyword overlap")

        scored.append(
            (
                confidence,
                {
                    "part_id": p.id,
                    "part_code": p.part_code,
                    "name": p.name,
                    "short_description": p.short_description,
                    "manufacturer": p.manufacturer,
                    "manufacturer_part_number": p.manufacturer_part_number,
                    "part_kind": p.part_kind,
                    "confidence": confidence,
                    "match_reason": "; ".join(reasons),
                },
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


# ---------------------------------------------------------------------------
# Storage suggestion
# ---------------------------------------------------------------------------

# Minimum Jaccard similarity between description tokens and a part's name
# tokens for that part to be considered "similar" when building the storage
# suggestion pool.  0.05 means at least one token in common out of ~20.
_MIN_STORAGE_SIMILARITY = 0.05

# Fixed confidence boost added to frequency-derived storage scores to ensure
# that even a single historical placement produces a non-trivial suggestion
# score (frequency score alone can round to zero for rare placements).
_STORAGE_CONFIDENCE_BOOST = 20


def _storage_score(count: int, total: int) -> int:
    """Compute a 0–100 storage suggestion confidence score.

    Combines a frequency-derived percentage with a fixed base boost, capped
    at 100 so the result is always a valid confidence value.
    """
    return min(100, int(count / total * 100) + _STORAGE_CONFIDENCE_BOOST)


async def suggest_storage(
    description: str,
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    limit: int = 3,
) -> list[dict]:
    """Suggest storage placements based on historical stock placement patterns.

    Strategy:
    1. Find parts whose names or descriptions are similar to *description*.
    2. Collect the location / container frequencies of their stock items.
    3. Return the most frequent placements as suggestions.

    Returns a list of dicts with keys: ``location_id``, ``container_id``,
    ``name``, ``score``, ``reason``.

    Uses raw SQL for placement lookups so the function works on both SQLite
    (testing) and PostgreSQL (production) without UUID type-binding issues.
    """
    from makervault.models.part import Part

    normed = normalise_description(description)

    # Load active parts using the ORM query (works on both backends)
    query = select(Part).where(Part.is_active.is_(True))
    if category_id is not None:
        query = query.where(Part.category_id == category_id)
    result = await db.execute(query)
    all_parts = result.scalars().all()

    # Identify similar parts by token overlap
    # Store IDs as normalised strings to avoid UUID dialect differences
    similar_id_strs: list[str] = []
    for p in all_parts:
        tok = _token_set(p.name) | _token_set(p.short_description)
        if _jaccard(set(normed.tokens), tok) >= _MIN_STORAGE_SIMILARITY:
            # Convert to string regardless of what the ORM returns (UUID or str)
            similar_id_strs.append(str(p.id))

    if not similar_id_strs:
        return []

    # Fetch stock placement for similar parts using raw SQL to avoid
    # UUID binding differences between PostgreSQL and SQLite.
    if len(similar_id_strs) == 1:
        stock_rows = (
            await db.execute(
                text(
                    "SELECT location_id, container_id FROM stock_items "
                    "WHERE part_id = :pid AND status = 'available'"
                ),
                {"pid": similar_id_strs[0]},
            )
        ).fetchall()
    else:
        placeholders = ", ".join(f":id{i}" for i in range(len(similar_id_strs)))
        params = {f"id{i}": v for i, v in enumerate(similar_id_strs)}
        stock_rows = (
            await db.execute(
                text(
                    f"SELECT location_id, container_id FROM stock_items "
                    f"WHERE part_id IN ({placeholders}) AND status = 'available'"
                ),
                params,
            )
        ).fetchall()

    location_counts: Counter = Counter()
    container_counts: Counter = Counter()
    for row in stock_rows:
        if row.location_id:
            location_counts[str(row.location_id)] += 1
        elif row.container_id:
            container_counts[str(row.container_id)] += 1

    if not location_counts and not container_counts:
        return []

    suggestions: list[dict] = []
    total = sum(location_counts.values()) + sum(container_counts.values()) or 1

    # Top locations — look up by raw SQL to avoid UUID type binding issues
    for loc_id_str, count in location_counts.most_common(limit):
        row = (
            await db.execute(
                text("SELECT name FROM locations WHERE id = :id"),
                {"id": loc_id_str},
            )
        ).fetchone()
        if row is None:
            continue
        suggestions.append(
            {
                "location_id": uuid.UUID(loc_id_str),
                "container_id": None,
                "name": row.name,
                "score": _storage_score(count, total),
                "reason": f"Used by {count} similar part(s)",
            }
        )

    # Top containers (fill remaining slots)
    remaining = limit - len(suggestions)
    for cont_id_str, count in container_counts.most_common(remaining):
        row = (
            await db.execute(
                text("SELECT name FROM containers WHERE id = :id"),
                {"id": cont_id_str},
            )
        ).fetchone()
        if row is None:
            continue
        suggestions.append(
            {
                "location_id": None,
                "container_id": uuid.UUID(cont_id_str),
                "name": row.name,
                "score": _storage_score(count, total),
                "reason": f"Used by {count} similar part(s)",
            }
        )

    suggestions.sort(key=lambda x: x["score"], reverse=True)
    return suggestions[:limit]


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_intake_match(
    description: str,
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
) -> dict:
    """Orchestrate: normalise + match + code + storage.

    Returns a dict matching the ``IntakeMatchResponse`` schema.
    """
    normed = normalise_description(description)
    candidates = await find_candidates(description, db, limit=5, category_id=category_id)
    suggested_code = await suggest_part_code(description, db)
    storage = await suggest_storage(description, db, category_id=category_id)

    return {
        "description": description,
        "normalised_tokens": normed.tokens,
        "candidates": candidates,
        "suggested_part_code": suggested_code,
        "storage_suggestions": storage,
    }
