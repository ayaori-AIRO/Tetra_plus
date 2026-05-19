void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(13, OUTPUT);

  digitalWrite(LED_BUILTIN, LOW);
  digitalWrite(13, LOW);

#if defined(TX_RX_LED_INIT)
  TX_RX_LED_INIT;
#endif
#if defined(TXLED1) && defined(RXLED1)
  TXLED1;
  RXLED1;
#endif
}

void loop() {
  digitalWrite(LED_BUILTIN, LOW);
  digitalWrite(13, LOW);

#if defined(TXLED1) && defined(RXLED1)
  TXLED1;
  RXLED1;
#endif
}
