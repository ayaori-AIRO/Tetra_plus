void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(13, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  digitalWrite(13, HIGH);
  delay(500);

  digitalWrite(LED_BUILTIN, LOW);
  digitalWrite(13, LOW);
  delay(500);
}
