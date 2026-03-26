const int relay1 = 4;
const int relay2 = 6;

void setup() {
  Serial.begin(9600);
  pinMode(relay1, OUTPUT);
  pinMode(relay2, OUTPUT);
  digitalWrite(relay1, LOW);
  digitalWrite(relay2, LOW);

}

void loop() {
  if(Serial.available()){
    char cmd = Serial.read();
    switch(cmd){
      case '1':
        digitalWrite(relay1, HIGH); // Turn relay 1 On
        break;
      case '2':
        digitalWrite(relay1,LOW); // Turn relay 1 OFF
        break;
      case '3':
        digitalWrite(relay2, HIGH); // Turn relay 2 On
        break;
      case '4':
        digitalWrite(relay2, LOW); // Turn relay 2 OFF
        break;
      case '5':
        digitalWrite(relay1, LOW); // Turn relay 1 OFF
        digitalWrite(relay2, LOW); // Turn relay 2 OFF
        break;
    }
  }
}
