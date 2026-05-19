#include <Adafruit_NeoPixel.h>

#define LED_PIN    5
#define LED_COUNT  30

#define INTERNAL_START 0
#define INTERNAL_END   19
#define CAMERA_START   20
#define CAMERA_END     23

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

void setRange(int startLed, int endLed, uint32_t color) {
  strip.clear();
  for (int i = startLed; i <= endLed; i++) {
    strip.setPixelColor(i, color);
  }
  strip.show();
}

void setup() {
  Serial.begin(9600);
  strip.begin();
  strip.clear();
  strip.show();
  strip.setBrightness(150);
  Serial.println("Ready");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "OFF") {
      strip.clear();
      strip.show();
      Serial.println("LED OFF");

    } else if (cmd == "INTERNAL") {
      setRange(INTERNAL_START, INTERNAL_END, strip.Color(255, 255, 255));
      Serial.println("INTERNAL LED ON");

    } else if (cmd == "CAMERA") {
      setRange(CAMERA_START, CAMERA_END, strip.Color(255, 255, 255));
      Serial.println("CAMERA LED ON");

    } else if (cmd.startsWith("PIXEL ")) {
      int led = constrain(cmd.substring(6).toInt(), 0, LED_COUNT - 1);
      strip.clear();
      strip.setPixelColor(led, strip.Color(255, 255, 255));
      strip.show();
      Serial.print("PIXEL LED ON ");
      Serial.println(led);
    }
  }
}
