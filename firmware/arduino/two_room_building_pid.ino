/*
  Single-Building PID Controller for Two-Heater Thermal System
  ------------------------------------------------------------
  - One PID loop controls the average building temperature
  - Both heaters receive the SAME duty cycle

  Status sent back to Python:
  TB=79.41,OUT=35.0,H1=1,H2=1
*/

const int heater1Pin = 4;
const int heater2Pin = 6;

// ---------- PID state ----------
struct PIDState {
  float sp;         // setpoint
  float kp;         // proportional gain
  float ki;         // integral gain
  float kd;         // derivative gain

  float pvRaw;      // raw process variable from serial
  float pvFilt;     // filtered process variable
  float iTerm;      // integral accumulator
  float prevPv;     // previous filtered PV for derivative
  float outputPct;  // output from 0 to 100%
};

PIDState building = {80.0f, 1.20f, 1.00f, 0.50f, 75.0f ,75.0f, 0.0f, 75.0f, 0.0f};

// ---------- Timing / Safety ----------
const unsigned long controlPeriodMs = 1000;   // PID update every 1 second
const unsigned long pwmWindowMs     = 30000;  // 30 s window for relays
const unsigned long serialTimeoutMs = 15000;  // shut down if no temp update in 15 s

const float inputFilterAlpha = 0.18f;         // 0 to 1, higher = less smoothing
const float highTempCutoffF  = 88.0f;         // safety cutoff

unsigned long lastControlMs      = 0;
unsigned long pwmWindowStartMs   = 0;
unsigned long lastSerialUpdateMs = 0;

// ---------- heater state ----------
bool heater1On = false;
bool heater2On = false;

// ---------- serial receive buffer ----------
String rxLine = "";

void setup() {
  Serial.begin(9600);

  pinMode(heater1Pin, OUTPUT);
  pinMode(heater2Pin, OUTPUT);

  digitalWrite(heater1Pin, LOW);
  digitalWrite(heater2Pin, LOW);

  pwmWindowStartMs = millis();
  lastSerialUpdateMs = millis();

  Serial.println("Single-building PID controller ready.");
}

void loop() {
  const unsigned long now = millis();

  readSerialLine(now);

  if (now - lastControlMs >= controlPeriodMs) {
    lastControlMs = now;
    updateControl();
    sendStatus();
  }

  applyTimeProportioning(now);
}

// ============================================================
// PID update
// ============================================================
void updateControl() {
  // Low-pass filter the incoming building temperature
  building.pvFilt += inputFilterAlpha * (building.pvRaw - building.pvFilt);

  // Fail-safe: stale serial input or overtemperature
  if ((millis() - lastSerialUpdateMs) > serialTimeoutMs || building.pvFilt >= highTempCutoffF) {
    building.outputPct = 0.0f;
    building.iTerm = 0.0f;
    return;
  }

  const float dt = controlPeriodMs / 1000.0f;
  const float error = building.sp - building.pvFilt;

  // Proportional term
  const float pTerm = building.kp * error;

  // Integral term
  building.iTerm += building.ki * error * dt;

  // Clamp integral to heating-only range
  if (building.iTerm > 100.0f) building.iTerm = 100.0f;
  if (building.iTerm < 0.0f)   building.iTerm = 0.0f;

  // Derivative on measurement
  const float dTerm = -building.kd * (building.pvFilt - building.prevPv) / dt;

  // Total output
  float output = pTerm + building.iTerm + dTerm;

  // Clamp to 0..100% for heating-only control
  if (output > 100.0f) output = 100.0f;
  if (output < 0.0f)   output = 0.0f;

  building.outputPct = output;
  building.prevPv = building.pvFilt;
}

// ============================================================
// Time-proportioning actuator
// ============================================================
void applyTimeProportioning(unsigned long now) {
  // Safety shutdown
  if ((millis() - lastSerialUpdateMs) > serialTimeoutMs || building.pvFilt >= highTempCutoffF) {
    digitalWrite(heater1Pin, LOW);
    digitalWrite(heater2Pin, LOW);
    heater1On = false;
    heater2On = false;
    return;
  }

  // Advance the window
  if (now - pwmWindowStartMs >= pwmWindowMs) {
    pwmWindowStartMs += pwmWindowMs;
  }

  const unsigned long elapsed = now - pwmWindowStartMs;
  const unsigned long onTime = (unsigned long)(building.outputPct * 0.01f * pwmWindowMs);

  const bool onNow = (elapsed < onTime);

  heater1On = onNow;
  heater2On = onNow;

  digitalWrite(heater1Pin, heater1On ? HIGH : LOW);
  digitalWrite(heater2Pin, heater2On ? HIGH : LOW);
}

// ============================================================
// Serial receive
// ============================================================
void readSerialLine(unsigned long now) {
  while (Serial.available()) {
    char c = (char)Serial.read();

    if (c == '\n') {
      parseLine(rxLine, now);
      rxLine = "";
    } else if (c != '\r') {
      rxLine += c;
    }
  }
}

// ============================================================
// Parse incoming lines
// ============================================================
void parseLine(const String &line, unsigned long now) {
  // Example: TB=79.52
  if (line.startsWith("TB=")) {
    float tb = line.substring(3).toFloat();

    if (tb > 32.0f && tb < 120.0f) {
      building.pvRaw = tb;
      lastSerialUpdateMs = now;
    }
    return;
  }

  // Example: SP=80.00
  if (line.startsWith("SP=")) {
    float sp = line.substring(3).toFloat();

    if (sp > 32.0f && sp < 120.0f) {
      building.sp = sp;
    }
    return;
  }

  // Example: G=20.0000,0.0100,0.0000
  if (line.startsWith("G=")) {
    int c1 = line.indexOf(',');
    int c2 = line.indexOf(',', c1 + 1);

    if (c1 > 0 && c2 > c1) {
      float kp = line.substring(2, c1).toFloat();
      float ki = line.substring(c1 + 1, c2).toFloat();
      float kd = line.substring(c2 + 1).toFloat();

      if (kp >= 0.0f && ki >= 0.0f && kd >= 0.0f) {
        building.kp = kp;
        building.ki = ki;
        building.kd = kd;
      }
    }
    return;
  }

  // Optional emergency off command
  if (line == "OFF") {
    building.outputPct = 0.0f;
    building.iTerm = 0.0f;
    digitalWrite(heater1Pin, LOW);
    digitalWrite(heater2Pin, LOW);
    heater1On = false;
    heater2On = false;
    return;
  }
}

// ============================================================
// Status output to Python
// ============================================================
void sendStatus() {
  Serial.print("TB=");
  Serial.print(building.pvFilt, 2);

  Serial.print(",OUT=");
  Serial.print(building.outputPct, 1);

  Serial.print(",H1=");
  Serial.print(heater1On ? 1 : 0);

  Serial.print(",H2=");
  Serial.println(heater2On ? 1 : 0);
}