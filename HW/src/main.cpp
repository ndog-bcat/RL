#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <esp_system.h>
#include "wifi_secrets.h"

constexpr int MOTOR_A = 25;
constexpr int MOTOR_B = 26;
constexpr int BUTTON = 27;
constexpr unsigned long TIMEOUT_MS = 1500;

WebServer server(80);
String bootId;
int speed = 0;
int direction = 1;
bool remoteMode = false;
unsigned long lastCommand = 0;

const int speedLevels[] = {0, 64, 128, 192, 255};
int speedIndex = 0;
bool lastRaw = false;
bool stablePressed = false;
unsigned long lastChange = 0;
unsigned long pressStart = 0;

int appliedSpeed = -1;
int appliedDirection = 1;

const char* resetReasonName(esp_reset_reason_t reason) {
    switch (reason) {
        case ESP_RST_POWERON:  return "POWERON";
        case ESP_RST_EXT:      return "EXTERNAL";
        case ESP_RST_SW:       return "SOFTWARE";
        case ESP_RST_PANIC:    return "PANIC";
        case ESP_RST_INT_WDT:  return "INT_WDT";
        case ESP_RST_TASK_WDT: return "TASK_WDT";
        case ESP_RST_WDT:      return "WDT";
        case ESP_RST_DEEPSLEEP:return "DEEPSLEEP";
        case ESP_RST_BROWNOUT: return "BROWNOUT";
        default:               return "OTHER";
    }
}

void setMotor(int pwm, int dir) {
    pwm = constrain(pwm, 0, 255);
    if (pwm == appliedSpeed && (pwm == 0 || dir == appliedDirection)) {
        return; // 같은 명령의 재전송은 PWM을 끊지 않음
    }

    analogWrite(MOTOR_A, 0);
    analogWrite(MOTOR_B, 0);
    if (pwm > 0) {
        analogWrite(dir == 1 ? MOTOR_A : MOTOR_B, pwm);
    }
    appliedSpeed = pwm;
    appliedDirection = dir;
}

void stopMotor() {
    speed = 0;
    remoteMode = false;
    setMotor(0, direction);
}

bool parsePwm(const String& input, int& result) {
    if (input.length() < 1 || input.length() > 3) return false;
    for (unsigned int i = 0; i < input.length(); ++i) {
        if (input[i] < '0' || input[i] > '9') return false;
    }
    result = input.toInt();
    return result >= 0 && result <= 255;
}

void handleMotorCommand() {
    if (!server.hasArg("speed") || !server.hasArg("dir")) {
        server.send(400, "text/plain", "Missing args");
        return;
    }
    int requestedSpeed;
    String d = server.arg("dir");
    if (!parsePwm(server.arg("speed"), requestedSpeed) ||
        (d != "1" && d != "-1")) {
        server.send(400, "text/plain", "Invalid args");
        return;
    }

    speed = requestedSpeed;
    direction = d.toInt();
    setMotor(speed, direction);
    remoteMode = speed > 0;
    lastCommand = millis();
    server.send(200, "text/plain", "OK");
}

void handleStatus() {
    String output = "{";
    output += "\"boot_id\":\"" + bootId + "\",";
    output += "\"uptime_ms\":" + String(millis()) + ",";
    output += "\"reset_reason\":\"" + String(resetReasonName(esp_reset_reason())) + "\",";
    output += "\"wifi_status\":" + String((int)WiFi.status()) + ",";
    output += "\"wifi_rssi_dbm\":" + String(WiFi.RSSI()) + ",";
    output += "\"motor_pwm\":" + String(speed) + ",";
    output += "\"motor_dir\":" + String(direction) + ",";
    output += "\"remote_mode\":" + String(remoteMode ? "true" : "false") + ",";
    output += "\"command_age_ms\":" +
        String(remoteMode ? (long)(millis() - lastCommand) : -1L);
    output += "}";
    server.send(200, "application/json", output);
}

void handleButton() {
    bool raw = (digitalRead(BUTTON) == LOW);
    if (raw != lastRaw) {
        lastChange = millis();
        lastRaw = raw;
    }
    if (millis() - lastChange <= 30 || raw == stablePressed) return;

    stablePressed = raw;
    if (raw) {
        pressStart = millis();
        return;
    }

    unsigned long duration = millis() - pressStart;
    if (duration >= 800) {
        direction *= -1;
    } else {
        speedIndex = (speedIndex + 1) % 5;
        speed = speedLevels[speedIndex];
    }
    remoteMode = false;
    setMotor(speed, direction);
}

void setup() {
    digitalWrite(MOTOR_A, LOW);
    digitalWrite(MOTOR_B, LOW);
    pinMode(MOTOR_A, OUTPUT);
    pinMode(MOTOR_B, OUTPUT);
    pinMode(BUTTON, INPUT_PULLUP);
    Serial.begin(115200);
    stopMotor();

    bootId = String(esp_random(), HEX);
    Serial.printf("BOOT_ID=%s RESET=%s\n", bootId.c_str(),
                  resetReasonName(esp_reset_reason()));

    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("Connecting to SSID: ");
    Serial.println(WIFI_SSID);

    unsigned long started = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - started < 30000) {
        delay(250);
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.print("ESP32 IP: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("Wi-Fi connection failed");
    }

    server.on("/motor", HTTP_GET, handleMotorCommand);
    server.on("/status", HTTP_GET, handleStatus);
    server.on("/stop", HTTP_GET, []() {
        stopMotor();
        server.send(200, "text/plain", "STOP");
    });
    server.begin();
    Serial.println("HTTP server started");
}

void loop() {
    server.handleClient();
    handleButton();
    if (remoteMode && millis() - lastCommand > TIMEOUT_MS) {
        stopMotor();
    }
    delay(1);
}
