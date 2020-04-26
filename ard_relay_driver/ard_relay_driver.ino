#define RELAY_CTRL_PIN 8
#define PI_INTERRUPT_PIN 2

volatile bool trigger = false;

void setup() {
  // put your setup code here, to run once:
  pinMode(RELAY_CTRL_PIN,  OUTPUT);
  pinMode(PI_INTERRUPT_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PI_INTERRUPT_PIN), handleInterrupt, RISING);
}

void handleInterrupt() {
  trigger = true;
}

void releaseBeer()
{
  digitalWrite(RELAY_CTRL_PIN, HIGH);
  delay(500);
  digitalWrite(RELAY_CTRL_PIN, LOW);
}

void loop() {
  // put your main code here, to run repeatedly:
  if (trigger) {
    releaseBeer();
    trigger = false;
  }
}
