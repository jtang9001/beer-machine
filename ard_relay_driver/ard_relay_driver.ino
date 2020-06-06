#define RELAY_PIN 8
#define PI_PIN 2

bool latch = true;

void setup() {
  // put your setup code here, to run once:
  pinMode(RELAY_PIN,  OUTPUT);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(PI_PIN, INPUT_PULLUP);
  digitalWrite(LED_BUILTIN, LOW);
  digitalWrite(RELAY_PIN, LOW);
}

void releaseBeer()
{
  digitalWrite(RELAY_PIN, HIGH);
  digitalWrite(LED_BUILTIN, HIGH);
  delay(500);
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(LED_BUILTIN, LOW);
}

void loop() {
  // put your main code here, to run repeatedly:
  if (digitalRead(PI_PIN) == LOW && latch) {
    delay(100);
    if digitalRead(PI_PIN == LOW) {
      delay(100);
      if digitalRead(PI_PIN == LOW) {
        releaseBeer();
        latch = false;
      }
    }
  }
  else if (digitalRead(PI_PIN) == HIGH) {
    latch = true;
  }
}
