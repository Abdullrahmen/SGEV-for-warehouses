class SimplePID{
  private:
    float kp, kd, ki, umax;   // Parameters
    float e_prev, e_integral; // Storage

  public:
    SimplePID() : kp(1), kd(0), ki(0), umax(255), e_prev(0), e_integral(0){}

    void setParams(float kpIn, float kdIn, float kiIn, float umaxIn){
      kp = kpIn; kd = kdIn; ki = kiIn; umax = umaxIn;
    }

    float error_value(int value, int target, float deltaT, int &power, int &dir){
      // error
      float e = target - value;
    
      // derivative
      float dvdt = (e-e_prev)/(deltaT);
    
      // integral
      e_integral = e_integral + e*deltaT;
    
      // control signal
      float u = kp*e + kd*dvdt + ki*e_integral;
      
      // motor power
      power = (int) fabs(u);
      if( power > umax ){
        power = umax;
      }

      dir = 1;
      if (u < 0)
        dir = -1;

      // store previous error
      e_prev = e;
      return u;
    }
};
////////////////////////// PINs nubmers /////////////////////////////
// FR, BR, FL, BL --> Front Right, Back Right, Front Left, Back Left
const int IN1[4] = {22, 22, 33, 33};
const int IN2[4] = {23, 23, 32, 32};
const int ENABLE[4] = {21, 16, 25, 19};
const int ENCODER_A[4] = {39, 17, 35, 13};
const int ENCODER_B[4] = {36, 4, 34, 14}; 

const float pid_kp = 1;
const float pid_ki = 0;
const float pid_kd = 0;

volatile int POS[4] = {0,0,0,0};
long prevT = 0;
SimplePID pid[4];



void setup(){
  Serial.begin(115200);

  for (int i = 0; i < 4; i++) {
    pinMode(IN1[i], OUTPUT);
    pinMode(IN2[i], OUTPUT);
    pinMode(ENABLE[i], INPUT);
    pinMode(ENCODER_A[i], INPUT);
    pinMode(ENCODER_B[i], INPUT);

    pid[i].setParams(pid_kp, pid_kd, pid_ki, 255);
    ledcAttachChannel(ENABLE[i], 10000, 8, i);
  } 
  // readEncoder template must be manual not in the loop
  attachInterrupt(ENCODER_A[0],readEncoder<0>,RISING);
  attachInterrupt(ENCODER_A[1],readEncoder<1>,RISING);
  attachInterrupt(ENCODER_A[2],readEncoder<2>,RISING);
  attachInterrupt(ENCODER_A[3],readEncoder<3>,RISING);

  Serial.println("target pos");
}

int target[4] = {0,0,0,0};
void loop(){
  // set target position
  for(int k = 0; k < 4; k++){
    if (sin((prevT/1e6)/4)>0){ // 4 seconds
      target[k] += 3; // ramp wave
      if (target[k] > 1500)
        target[k] = 1500;
    }else{
      target[k] -= 3;
      if (target[k] < -1500)
        target[k] = -1500;
    }
  }

   // time difference
  long currT = micros();
  float deltaT = ((long) (currT - prevT))/( 1.0e6 );
  prevT = currT;

  // Read the position
  int pos[4];
  noInterrupts(); // disable interrupts temporarily while reading
  for(int k = 0; k < 4; k++){
      pos[k] = POS[k];
    }
  interrupts(); // turn interrupts back on
  float u[4];
  // loop through the motors
  for(int k = 0; k < 4; k++){
    int power, dir;
    // evaluate the control signal
    u[k] = pid[k].error_value(pos[k],target[k],deltaT,power,dir);
    // signal the motor
    setMotor(dir,power,k,IN1[k],IN2[k]);
  }
  Serial.print(" ");              // Separator
  Serial.print(-2000);            // Dummy Min value (forces Y-min to -1000)
  Serial.print(" ");              // Separator
  Serial.print(2000);             // Dummy Max value (forces Y-max to 1000)
  Serial.print(" ");              // Separator

  for(int k = 0; k < 4; k++){
    Serial.print(target[k]);
    Serial.print(" ");
    Serial.print(pos[k]);
    Serial.print(" ");
    // Serial.print(u[k]);
    // Serial.print(" ");
  }
  Serial.println();
}

void setMotor(int dir, int pwmVal, int pwm_channel, int in1, int in2){
  //analogWrite(pwm,pwmVal);
  pwmVal = map(pwmVal, 0, 255, 100, 250);
  ledcWriteChannel(pwm_channel, pwmVal);
  if(dir == 1){
    digitalWrite(in1,HIGH);
    digitalWrite(in2,LOW);
  }
  else if(dir == -1){
    digitalWrite(in1,LOW);
    digitalWrite(in2,HIGH);
  }
  else{
    digitalWrite(in1,LOW);
    digitalWrite(in2,LOW);
  }  
}

template <int j>
void readEncoder(){
  int b = digitalRead(ENCODER_B[j]);
  if (b > 0)
    POS[j]++;
  else
    POS[j]--;
}