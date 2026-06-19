# Biometric Attendance & Check-In System

A high-performance biometric attendance application built with Python, OpenCV, MediaPipe, and face_recognition. The system automates check-ins using facial mapping alongside responsive hand gestures, syncing logs in real-time to a secure MySQL database backend.

## 🚀 Key Features
* **Dual Biometric Processing:** Tracks facial encodings for user identification while utilizing MediaPipe for zero-touch gesture actions.
* **Smart Gesture Controls:** * Open Full Palm ✋ -> Triggers student profile registration.
  * Thumbs Up 👍 -> Processes automatic Clock-In / Clock-Out.
* **4-Hour Session Lockout:** Prevents accidental or early check-outs by strictly calculating remaining duration down to the minute.
* **Modern Database Handshake:** Configured for native compatibility with modern database authentication engines.

---

## 🏗️ System Architecture & Workflow



1. **Video Stream:** OpenCV captures video frame pipelines and reduces frame overhead to conserve system CPU.
2. **Face & Gesture Detection:** Core features isolate bounding boxes for face encodings while tracking finger landmark nodes.
3. **Database Evaluation:** System processes validation requests directly against a background MySQL server instance.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
Ensure you have Git, Python 3.10+, and a running instance of MySQL installed.

### 2. Repository Deployment
```bash
git clone [https://github.com/biswajitkumarbehu/biometric-attendance-system.git](https://github.com/biswajitkumarbehu/biometric-attendance-system.git)
cd biometric-attendance-system