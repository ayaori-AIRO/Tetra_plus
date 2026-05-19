#include <Adafruit_NeoPixel.h>

#define LED_PIN    5
#define LED_COUNT  30

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

int readToken(String text, int tokenIndex) {
  int start = 0;
  int current = 0;

  text.trim();
  while (start < text.length()) {
    int end = text.indexOf(' ', start);
    if (end == -1) {
      end = text.length();
    }

    if (current == tokenIndex) {
      return text.substring(start, end).toInt();
    }

    current++;
    start = end + 1;
    while (start < text.length() && text.charAt(start) == ' ') {
      start++;
    }
  }

  return 0;
}

void setAll(uint32_t color) {
  for (int i = 0; i < strip.numPixels(); i++) {
    strip.setPixelColor(i, color);
  }
  strip.show();
}

void setRange(int startLed, int endLed, int red, int green, int blue) {
  startLed = constrain(startLed, 0, LED_COUNT - 1);
  endLed = constrain(endLed, 0, LED_COUNT - 1);

  if (startLed > endLed) {
    int temp = startLed;
    startLed = endLed;
    endLed = temp;
  }

  strip.clear();
  for (int i = startLed; i <= endLed; i++) {
    strip.setPixelColor(i, strip.Color(red, green, blue));
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

    if (cmd == "ON") {
      setAll(strip.Color(255, 255, 255));
      Serial.println("LED ON");

    } else if (cmd == "OFF") {
      strip.clear();
      strip.show();
      Serial.println("LED OFF");

    } else if (cmd.startsWith("RANGE ")) {
      int startLed = readToken(cmd, 1);
      int endLed = readToken(cmd, 2);
      int red = constrain(readToken(cmd, 3), 0, 255);
      int green = constrain(readToken(cmd, 4), 0, 255);
      int blue = constrain(readToken(cmd, 5), 0, 255);

      setRange(startLed, endLed, red, green, blue);
      Serial.print("LED RANGE ");
      Serial.print(startLed);
      Serial.print(" ");
      Serial.println(endLed);
    }
  }
}
