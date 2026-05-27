#include <Adafruit_NeoPixel.h>

#define LED_PIN    5
#define LED_COUNT  30

#define INTERNAL_START 0
#define INTERNAL_END   19
#define CAMERA_START   20
#define CAMERA_END     23

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

int internalRed = 0;
int internalGreen = 0;
int internalBlue = 0;
int cameraRed = 0;
int cameraGreen = 0;
int cameraBlue = 0;

String readToken(String text, int tokenIndex) {
  int start = 0;
  int current = 0;

  text.trim();
  while (start < text.length()) {
    int end = text.indexOf(' ', start);
    if (end == -1) {
      end = text.length();
    }

    if (current == tokenIndex) {
      return text.substring(start, end);
    }

    current++;
    start = end + 1;
    while (start < text.length() && text.charAt(start) == ' ') {
      start++;
    }
  }

  return "";
}

int readColorToken(String cmd, int tokenIndex, int fallback) {
  String token = readToken(cmd, tokenIndex);
  if (token.length() == 0) {
    return fallback;
  }

  return constrain(token.toInt(), 0, 255);
}

void setRange(int startLed, int endLed, uint32_t color) {
  for (int i = startLed; i <= endLed; i++) {
    strip.setPixelColor(i, color);
  }
}

void renderRanges() {
  strip.clear();
  setRange(
    INTERNAL_START,
    INTERNAL_END,
    strip.Color(internalRed, internalGreen, internalBlue)
  );
  setRange(
    CAMERA_START,
    CAMERA_END,
    strip.Color(cameraRed, cameraGreen, cameraBlue)
  );
  strip.show();
}

void setup() {
  Serial.begin(9600);
  strip.begin();
  strip.clear();
  strip.show();
  strip.setBrightness(255);
  Serial.println("Ready");
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "OFF") {
      internalRed = 0;
      internalGreen = 0;
      internalBlue = 0;
      cameraRed = 0;
      cameraGreen = 0;
      cameraBlue = 0;
      renderRanges();
      Serial.println("LED OFF");

    } else if (cmd == "INTERNAL" || cmd.startsWith("INTERNAL ")) {
      internalRed = readColorToken(cmd, 1, 255);
      internalGreen = readColorToken(cmd, 2, internalRed);
      internalBlue = readColorToken(cmd, 3, internalRed);
      renderRanges();
      Serial.print("INTERNAL ");
      Serial.print(internalRed);
      Serial.print(" ");
      Serial.print(internalGreen);
      Serial.print(" ");
      Serial.println(internalBlue);

    } else if (cmd == "CAMERA" || cmd.startsWith("CAMERA ")) {
      cameraRed = readColorToken(cmd, 1, 255);
      cameraGreen = readColorToken(cmd, 2, cameraRed);
      cameraBlue = readColorToken(cmd, 3, cameraRed);
      renderRanges();
      Serial.print("CAMERA ");
      Serial.print(cameraRed);
      Serial.print(" ");
      Serial.print(cameraGreen);
      Serial.print(" ");
      Serial.println(cameraBlue);

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
