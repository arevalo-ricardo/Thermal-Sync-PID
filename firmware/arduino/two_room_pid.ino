// Minimal-change Arduino controller for two-room PID heating
// Replaces relay bang-bang commands with serial temperature input + time-proportioning outputs

const int heater1Pin = 4;
const int heater2Pin = 6;

struct PIDState {
  float sp;
  float kp;
  float ki;
  float kd;
  float pvRaw;
  float pvFilt;
  float iTerm;
  float prevPv;
  float outputPct;
  bool heaterOn;
};

PIDState rm1 = {80.0f, 100.0f, 0.20f, 0.0f, 75.0f, 75.0f, 0.0f, 75.0f, 0.0f, false};
PIDState rm2 = {80.0f, 100.0f, 0.20f, 0.0f, 75.0f, 75.0f, 0.0f, 75.0f, 0.0f, false};

const unsigned long controlPeriodMs = 1000;
const unsigned long pwmWindowMs = 10000;
const unsigned long serialTimeoutMs = 15000;
const float inputFilterAlpha = 0.15f;
const float highTempCutoffF = 88.0f;

unsigned long lastControlMs = 0;
unsigned long pwmWindowStartMs = 0;
unsigned long lastSerialUpdateMs = 0;

String rxLine = "";

void setup() {
  Serial.begin(9600);
  pinMode(heater1Pin, OUTPUT);
  pinMode(heater2Pin, OUTPUT);
  digitalWrite(heater1Pin, LOW);
  digitalWrite(heater2Pin, LOW);
  pwmWindowStartMs = millis();
}

void loop() {
  const unsigned long now = millis();
  readSerialLine(now);

  if (now - lastControlMs >= controlPeriodMs) {
    lastControlMs = now;
    updateControl(rm1);
    updateControl(rm2);
    sendStatus();
  }

  applyTimeProportioning(now);
}

void updateControl(PIDState &ch) {
  ch.pvFilt += inputFilterAlpha * (ch.pvRaw - ch.pvFilt);

  // Fail-safe conditions
  if ((millis() - lastSerialUpdateMs) > serialTimeoutMs || ch.pvFilt >= highTempCutoffF) {
    ch.outputPct = 0.0f;
    ch.iTerm = 0.0f;
    return;
  }

  const float dt = controlPeriodMs / 1000.0f;
  const float error = ch.sp - ch.pvFilt;
  const float pTerm = ch.kp * error;

  ch.iTerm += ch.ki * error * dt;
  if (ch.iTerm > 100.0f) ch.iTerm = 100.0f;
  if (ch.iTerm < 0.0f) ch.iTerm = 0.0f;

  const float dTerm = -ch.kd * (ch.pvFilt - ch.prevPv) / dt;
  float output = pTerm + ch.iTerm + dTerm;

  if (output > 100.0f) output = 100.0f;
  if (output < 0.0f) output = 0.0f;

  ch.outputPct = output;
  ch.prevPv = ch.pvFilt;
}

void applyTimeProportioning(unsigned long now) {
  if ((millis() - lastSerialUpdateMs) > serialTimeoutMs || rm1.pvFilt >= highTempCutoffF || rm2.pvFilt >= highTempCutoffF) {
    digitalWrite(heater1Pin, LOW);
    digitalWrite(heater2Pin, LOW);
    rm1.heaterOn = false;
    rm2.heaterOn = false;
    return;
  }

  if (now - pwmWindowStartMs >= pwmWindowMs) {
    pwmWindowStartMs += pwmWindowMs;
  }

  const unsigned long elapsed = now - pwmWindowStartMs;
  const unsigned long onTime1 = (unsigned long)(rm1.outputPct * 0.01f * pwmWindowMs);
  const unsigned long onTime2 = (unsigned long)(rm2.outputPct * 0.01f * pwmWindowMs);

  rm1.heaterOn = elapsed < onTime1;
  rm2.heaterOn = elapsed < onTime2;

  digitalWrite(heater1Pin, rm1.heaterOn ? HIGH : LOW);
  digitalWrite(heater2Pin, rm2.heaterOn ? HIGH : LOW);
}

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

void parseLine(const String &line, unsigned long now) {
  // Temperature update format from Python:
  // T1=79.25,T2=78.90
  if (line.startsWith("T1=")) {
    int commaIdx = line.indexOf(',');
    int t2Idx = line.indexOf("T2=");
    if (commaIdx > 0 && t2Idx > commaIdx) {
      float t1 = line.substring(3, commaIdx).toFloat();
      float t2 = line.substring(t2Idx + 3).toFloat();
      if (t1 > 32.0f && t1 < 120.0f && t2 > 32.0f && t2 < 120.0f) {
        rm1.pvRaw = t1;
        rm2.pvRaw = t2;
        lastSerialUpdateMs = now;
      }
    }
    return;
  }

  // Optional Setpoint Update from "PID Temperature Logging" Script 
  // SP1=80.0,SP2=80.0
  if (line.startsWith("SP1=")) {
    int commaIdx = line.indexOf(',');
    int sp2Idx = line.indexOf("SP2=");
    if (commaIdx > 0 && sp2Idx > commaIdx) {
      float sp1 = line.substring(4, commaIdx).toFloat();
      float sp2 = line.substring(sp2Idx + 4).toFloat();
      if (sp1 > 32.0f && sp1 < 120.0f) rm1.sp = sp1;
      if (sp2 > 32.0f && sp2 < 120.0f) rm2.sp = sp2;
    }
    return;
  }

  // Optional Gain Update from "PID Temperature Logging" Script
  // G1=8.0,0.03,0.0
  // G2=8.0,0.03,0.0
  if (line.startsWith("G1=") || line.startsWith("G2=")) {
    PIDState *ch = line.startsWith("G1=") ? &rm1 : &rm2;
    int eq = line.indexOf('=');
    int c1 = line.indexOf(',', eq + 1);
    int c2 = line.indexOf(',', c1 + 1);
    if (eq > 0 && c1 > eq && c2 > c1) {
      ch->kp = line.substring(eq + 1, c1).toFloat();
      ch->ki = line.substring(c1 + 1, c2).toFloat();
      ch->kd = line.substring(c2 + 1).toFloat();
    }
    return;
  }
}

void sendStatus() {
  Serial.print("PV1=");
  Serial.print(rm1.pvFilt, 2);
  Serial.print(",OUT1=");
  Serial.print(rm1.outputPct, 1);
  Serial.print(",H1=");
  Serial.print(rm1.heaterOn ? 1 : 0);

  Serial.print(",PV2=");
  Serial.print(rm2.pvFilt, 2);
  Serial.print(",OUT2=");
  Serial.print(rm2.outputPct, 1);
  Serial.print(",H2=");
  Serial.println(rm2.heaterOn ? 1 : 0);
}
