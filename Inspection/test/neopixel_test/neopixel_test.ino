#include <Adafruit_NeoPixel.h>

#define LED_PIN    5
#define LED_COUNT  30

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

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

    if (cmd == "ON") {
      for (int i = 0; i < strip.numPixels(); i++)
        strip.setPixelColor(i, strip.Color(255, 255, 255));
      strip.show();
      Serial.println("LED ON");

    } else if (cmd == "OFF") {
      strip.clear();
      strip.show();
      Serial.println("LED OFF");
    }
  }
}
