const int IN1[4] = {23, 23, 32, 32};
const int IN2[4] = {22, 22, 33, 33};
const int ENABLE[4] = {21, 16, 25, 19};
const int ENCODER_A[4] = {36, 4, 35, 14};
const int ENCODER_B[4] = {39, 17, 34, 13}; 

volatile int POS[4] = {0,0,0,0};

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < 4; i++) {
    pinMode(IN1[i], OUTPUT);
    pinMode(IN2[i], OUTPUT);
    pinMode(ENABLE[i], INPUT);
    pinMode(ENCODER_A[i], INPUT);
    pinMode(ENCODER_B[i], INPUT);

    //pid[i].setParams(1,0,0,255);
    ledcAttachChannel(ENABLE[i], 10000, 8, i);
  } 
  // readEncoder template must be manual not in the loop
  attachInterrupt(ENCODER_A[0],readEncoder<0>,RISING);
  attachInterrupt(ENCODER_A[1],readEncoder<1>,RISING);
  attachInterrupt(ENCODER_A[2],readEncoder<2>,RISING);
  attachInterrupt(ENCODER_A[3],readEncoder<3>,RISING);

  Serial.println("target pos");
}

void loop() {
  // Run Code
  for(int i = 0; i < 4; i++){
    ledcWriteChannel(i, 200);
    digitalWrite(IN1[i],LOW);
    digitalWrite(IN2[i],HIGH);
  }
  delay(1000);
  Serial.println(IN1[0]);
  for(int i = 0; i < 4; i++){
    digitalWrite(IN1[i],LOW);
    digitalWrite(IN2[i],LOW);
  }
  //Serial.println (Pos); Send the position via serial communication
  delay(1000);
  for(int i = 0; i < 4; i++){
    digitalWrite(IN1[i],HIGH);
    digitalWrite(IN2[i],LOW);
  }
  delay(1000);
  Serial.println(IN1[0]);
  for(int i = 0; i < 4; i++){
    digitalWrite(IN1[i],LOW);
    digitalWrite(IN2[i],LOW);
  }
  delay(1000);
}

template <int j>
void readEncoder(){
  int b = digitalRead(ENCODER_B[j]);
  if (b > 0)
    POS[j]++;
  else
    POS[j]--;
  
  Serial.println(POS[j]);
}