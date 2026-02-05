#define NUM_MOTORS 4

/* ================= USER PARAMETERS ================= */

const float Ts = 0.01;                 // Sampling time [s]
const float PWM_MAX = 255.0;
const float PWM_MIN = -255.0;
const float DEAD_ZONE = 140.0;

const int COUNTS_PER_REV = 750;

// FR, BR, FL, BL --> Front Right, Back Right, Front Left, Back Left

float speed[4] = {0, 0, 0, 0};
float speed_filt[4] = {0, 0, 0, 0};
float speed_prev[4] = {0, 0, 0, 0};

/* Encoder pins (A, B) */
const int ENC_A[NUM_MOTORS] = {39, 36, 32, 33};
const int ENC_B[NUM_MOTORS] = {34, 35, 21, 19};

/* Motor driver pins (H-Bridge: IN1, IN2, PWM) */
const int IN1[NUM_MOTORS] = {2, 2, 16, 16};
const int IN2[NUM_MOTORS] = {15, 15, 4, 4};
const int PWM_PINS[NUM_MOTORS] = {25, 26, 27, 14};

/* PWM settings */
const int PWM_CHANNELS[NUM_MOTORS] = {0, 1, 2, 3};
const int PWM_FREQ = 20000;
const int PWM_RES  = 8;

/* ================= PI CONTROLLER STRUCT ================= */

typedef struct {
  float Kp;
  float Ki;
  float ui;
  float e;
  float u;
} PI_Controller;

/* ================= PI CONTROLLERS (FROM MATLAB) ================= */

PI_Controller motorPI[NUM_MOTORS] = {
  {1.33, 7.65, 0, 0, 0},   
  {0.621, 7.9, 0, 0, 0},  
  {0.247, 7.85, 0, 0, 0},  
  {0.579, 7.91, 0, 0, 0}   
};

/* ================= ENCODER VARIABLES ================= */

volatile long encoderCount[NUM_MOTORS] = {0};

/* ================= QUADRATURE ISR ================= */

void IRAM_ATTR encoderISR(int id) {
  bool A = digitalRead(ENC_A[id]);
  bool B = digitalRead(ENC_B[id]);

  if (A == B)
    encoderCount[id]++;
  else
    encoderCount[id]--;
}

void IRAM_ATTR encoderISR0() { encoderISR(0); }
void IRAM_ATTR encoderISR1() { encoderISR(1); }
void IRAM_ATTR encoderISR2() { encoderISR(2); }
void IRAM_ATTR encoderISR3() { encoderISR(3); }

/* ================= UTILITY FUNCTIONS ================= */

float saturate(float u) {
  if (u > PWM_MAX) return PWM_MAX;
  if (u < PWM_MIN) return PWM_MIN;
  return u;
}

float deadZoneCompensation(float u) {
  if (u > 0 && u < DEAD_ZONE) return DEAD_ZONE;
  if (u < 0 && u > -DEAD_ZONE) return -DEAD_ZONE;
  return u;
}

/* ================= DISCRETE PI CONTROLLER ================= */

float PI_Update(PI_Controller *c, float reference, float feedback) {

  c->e = reference - feedback;

  float up = c->Kp * c->e;
  float ui_new = c->ui + (c->Ki * Ts * c->e);

  float u_unsat = up + ui_new;
  float u_sat   = saturate(u_unsat);

  /* Anti-windup */
  if (u_unsat == u_sat) {
    c->ui = ui_new;
  }

  u_sat = deadZoneCompensation(u_sat);
  c->u = u_sat;

  return c->u;
}

/* ================= SPEED COMPUTATION ================= */
/* Returns speed in RPM */

float readEncoderSpeed(int motorID) {

  static long lastCount[NUM_MOTORS] = {0};

  long count = encoderCount[motorID];
  long delta = count - lastCount[motorID];
  lastCount[motorID] = count;

  float rpm = (delta / (float)COUNTS_PER_REV) * (60.0 / Ts);

  //Low pass filtter (25 Hz cutoff)

  speed_filt[motorID] = 0.9*speed_filt[motorID] + 0.05*rpm + 0.05*speed_prev[motorID];
  speed_prev[motorID] = speed_filt[motorID];
  return rpm;
}

/* ================= MOTOR DRIVER ================= */

void setMotorPWM(int motorID, float pwmValue) {

  int pwm = abs((int)pwmValue);
  pwm = constrain(pwm, 0, 255);

  if (pwmValue >= 0) {
    digitalWrite(IN1[motorID], HIGH);
    digitalWrite(IN2[motorID], LOW);
  } else {
    digitalWrite(IN1[motorID], LOW);
    digitalWrite(IN2[motorID], HIGH);
  }

  ledcWrite(PWM_PINS[motorID], pwm);
}

/* ================= SETUP ================= */

void setup() {

   Serial.begin(115200);
  
  /* Motor pins */
  for (int i = 0; i < NUM_MOTORS; i++) {
    pinMode(IN1[i], OUTPUT);
    pinMode(IN2[i], OUTPUT);

    ledcAttachChannel(PWM_PINS[i], PWM_FREQ, PWM_RES, PWM_CHANNELS[i]);
  }

  /* Encoder pins */
  for (int i = 0; i < NUM_MOTORS; i++) {
    pinMode(ENC_A[i], INPUT_PULLUP);
    pinMode(ENC_B[i], INPUT_PULLUP);
  }

  attachInterrupt(digitalPinToInterrupt(ENC_A[0]), encoderISR0, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_A[1]), encoderISR1, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_A[2]), encoderISR2, CHANGE);
  attachInterrupt(digitalPinToInterrupt(ENC_A[3]), encoderISR3, CHANGE);
}

/* ================= MAIN LOOP ================= */

void loop() {

  static unsigned long lastTime = 0;
  unsigned long now = millis();

  if (now - lastTime >= Ts * 1000) {
    lastTime = now;

    /* ===== MASTER REFERENCES (RPM) ===== */
    float left_ref  = 80.0;
    float right_ref = 80.0;

    //ٌRight Master (RB)

    speed[1] = readEncoderSpeed(1);
    float pwm1   = PI_Update(&motorPI[1], right_ref, speed[1]);
    setMotorPWM(1, pwm1);

    Serial.print(speed[1]);
    Serial.print(" ");

    //Right Slave (RF)

    speed[0] = readEncoderSpeed(0);
    float pwm0   = PI_Update(&motorPI[0], speed[1], speed[0]);
    setMotorPWM(0, pwm0);

    Serial.print(speed[0]);
    Serial.print(" ");

    //Left Master (LB)

    speed[3] = readEncoderSpeed(3);
    float pwm3   = PI_Update(&motorPI[3], left_ref, speed[3]);
    setMotorPWM(3, pwm3);

    Serial.print(speed[3]);
    Serial.print(" ");

    //Left Slave (LF)

    speed[2] = readEncoderSpeed(2);
    float pwm2   = PI_Update(&motorPI[2], speed[3], speed[2]);
    setMotorPWM(2, pwm2);

    Serial.print(speed[2]);
    Serial.print(" ");

    /*float reference[NUM_MOTORS] = {
      left_ref, left_ref,
      right_ref, right_ref
    };

    for (int i = 0; i < NUM_MOTORS; i++) {
      speed[i] = readEncoderSpeed(i);
      float pwm   = PI_Update(&motorPI[i], reference[i], speed[i]);
      setMotorPWM(i, pwm);

      Serial.print(speed[i]);
      Serial.print(" ");
    }*/
    Serial.println();
  }
}
