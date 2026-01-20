const ADMIN_KEY = "taha-admin";
const LEGACY_ADMIN_KEY = "taha-admin-password";
const ADMIN_LIST_KEY = "taha-admins";

const setupModal = document.getElementById("admin-setup-modal");
const setupClose = document.getElementById("admin-setup-close");
const setupSave = document.getElementById("admin-setup-save");
const setupStatus = document.getElementById("admin-setup-status");
const nameInput = document.getElementById("admin-name");
const emailInput = document.getElementById("admin-email");
const passwordInput = document.getElementById("admin-password");
const passwordConfirmInput = document.getElementById("admin-password-confirm");

const loginModal = document.getElementById("admin-login-modal");
const loginClose = document.getElementById("admin-login-close");
const loginEmail = document.getElementById("admin-login-email");
const loginPassword = document.getElementById("admin-login-password");
const loginStatus = document.getElementById("admin-login-status");
const loginSubmit = document.getElementById("admin-login-submit");
const loginToggle = document.getElementById("admin-login-toggle");
const robot = document.getElementById("admin-robot");
const robotMessage = document.getElementById("robot-message");
const robotEyes = robot ? robot.querySelectorAll(".robot__eye") : [];
const robotEyeLeft = robot ? robot.querySelector(".robot__eye--left") : null;
const robotEyeRight = robot ? robot.querySelector(".robot__eye--right") : null;

const successModal = document.getElementById("admin-success-modal");
const successClose = document.getElementById("admin-success-close");
const successCta = document.getElementById("admin-success-cta");
const successTitle = document.getElementById("admin-success-title");
const successMessage = document.getElementById("admin-success-message");

const recoverModal = document.getElementById("admin-recover-modal");
const recoverClose = document.getElementById("admin-recover-close");
const recoverEmail = document.getElementById("recover-email");
const recoverEmailStatus = document.getElementById("recover-email-status");
const recoverSendOtp = document.getElementById("recover-send-otp");
const recoverOtp = document.getElementById("recover-otp");
const recoverOtpHint = document.getElementById("recover-otp-hint");
const recoverOtpStatus = document.getElementById("recover-otp-status");
const recoverVerifyOtp = document.getElementById("recover-verify-otp");
const recoverPassword = document.getElementById("recover-password");
const recoverPasswordConfirm = document.getElementById("recover-password-confirm");
const recoverPasswordStatus = document.getElementById("recover-password-status");
const recoverSavePassword = document.getElementById("recover-save-password");
const recoverStepEmail = document.getElementById("recover-step-email");
const recoverStepOtp = document.getElementById("recover-step-otp");
const recoverStepPassword = document.getElementById("recover-step-password");
const forgotBtn = document.getElementById("admin-forgot-btn");
const logoutBtn = document.getElementById("admin-logout-btn");
const adminAccountsOpen = document.getElementById("admin-accounts-open");

let recoveryOtp = "";
let adminLocked = false;

function isAdminSessionActive() {
  try {
    return localStorage.getItem("taha-admin-session") === "active";
  } catch (error) {
    return false;
  }
}

function setAdminSession(active) {
  try {
    if (active) {
      localStorage.setItem("taha-admin-session", "active");
    } else {
      localStorage.removeItem("taha-admin-session");
    }
  } catch (error) {
    // Ignore storage failures.
  }
}

function lockAdmin() {
  adminLocked = true;
  document.body.classList.add("admin-locked");
  if (setupClose) {
    setupClose.style.display = "none";
  }
  if (loginClose) {
    loginClose.style.display = "none";
  }
}

function unlockAdmin() {
  adminLocked = false;
  document.body.classList.remove("admin-locked");
  if (setupClose) {
    setupClose.style.display = "";
  }
  if (loginClose) {
    loginClose.style.display = "";
  }
}

function openModal(el) {
  if (!el) return;
  el.classList.add("show");
  el.setAttribute("aria-hidden", "false");
}

function closeModal(el) {
  if (!el) return;
  el.classList.remove("show");
  el.setAttribute("aria-hidden", "true");
}

function getStoredAdmin() {
  try {
    const raw = localStorage.getItem(ADMIN_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (error) {
    return null;
  }
}

function setStoredAdmin(value) {
  try {
    localStorage.setItem(ADMIN_KEY, JSON.stringify(value));
  } catch (error) {
    // Ignore storage failures.
  }
}

function getAdminList() {
  try {
    const raw = localStorage.getItem(ADMIN_LIST_KEY);
    const list = raw ? JSON.parse(raw) : [];
    if (Array.isArray(list)) {
      return list;
    }
  } catch (error) {
    return [];
  }
  return [];
}

function setAdminList(list) {
  try {
    localStorage.setItem(ADMIN_LIST_KEY, JSON.stringify(list));
  } catch (error) {
    // Ignore storage failures.
  }
}

function upsertAdminList(admin) {
  if (!admin || !admin.email) return;
  const list = getAdminList();
  const normalized = admin.email.toLowerCase();
  const existingIndex = list.findIndex((item) => item.email && item.email.toLowerCase() === normalized);
  if (existingIndex >= 0) {
    list[existingIndex] = {
      ...admin,
      createdAt: list[existingIndex].createdAt || admin.createdAt,
    };
  } else {
    const createdAt = admin.createdAt || new Date().toISOString();
    list.push({ ...admin, createdAt });
  }
  setAdminList(list);
}


function validatePasswords() {
  const name = (nameInput && nameInput.value) || "";
  const email = (emailInput && emailInput.value) || "";
  const password = (passwordInput && passwordInput.value) || "";
  const confirm = (passwordConfirmInput && passwordConfirmInput.value) || "";
  if (!name.trim()) {
    return "Name is required.";
  }
  if (!email.trim()) {
    return "Email is required.";
  }
  if (!password || password.length < 4) {
    return "Password must be at least 4 characters.";
  }
  if (password !== confirm) {
    return "Passwords do not match.";
  }
  return "";
}

function handleSave() {
  if (!setupStatus) return;
  const error = validatePasswords();
  if (error) {
    setupStatus.textContent = error;
    return;
  }
  const admin = {
    name: nameInput.value.trim(),
    email: emailInput.value.trim(),
    password: passwordInput.value,
    createdAt: new Date().toISOString(),
  };
  setStoredAdmin(admin);
  upsertAdminList(admin);
  setupStatus.textContent = "";
  closeModal(setupModal);
  unlockAdmin();
  setAdminSession(true);
  if (successTitle) successTitle.textContent = "Successfully created admin";
  if (successMessage) successMessage.textContent = "Your admin password has been saved.";
  openModal(successModal);
}

function showLoginModal() {
  if (!loginModal) return;
  if (loginStatus) loginStatus.textContent = "";
  if (loginEmail) loginEmail.value = "";
  if (loginPassword) loginPassword.value = "";
  if (loginPassword) loginPassword.type = "password";
  if (loginToggle) loginToggle.setAttribute("aria-label", "Show password");
  setRobotState("neutral");
  openModal(loginModal);
  if (loginEmail) {
    loginEmail.focus();
  }
}

function handleLogin() {
  if (!loginStatus) return;
  const admin = getStoredAdmin();
  if (!admin) {
    loginStatus.textContent = "Admin account not found.";
    setRobotState("sad");
    return;
  }
  const email = (loginEmail && loginEmail.value.trim()) || "";
  const password = (loginPassword && loginPassword.value) || "";
  if (!email || !password) {
    loginStatus.textContent = "Email and password are required.";
    setRobotState("sad");
    return;
  }
  if (admin.email.toLowerCase() !== email.toLowerCase() || admin.password !== password) {
    loginStatus.textContent = "Invalid email or password.";
    setRobotState("sad");
    return;
  }
  loginStatus.textContent = "";
  closeModal(loginModal);
  unlockAdmin();
  setAdminSession(true);
  setRobotState("smile");
  showWelcomeOverlay();
}

function setRobotState(state) {
  if (!robot) return;
  robot.classList.remove("smile", "sad", "eyes-closed", "one-eye");
  resetRobotEyes();
  if (state === "smile") {
    robot.classList.add("smile");
  } else if (state === "sad") {
    robot.classList.add("sad");
    if (robotMessage) robotMessage.textContent = "Try again";
  } else if (state === "eyes-closed") {
    robot.classList.add("eyes-closed");
  } else if (state === "one-eye") {
    robot.classList.add("one-eye");
  }
}

function trackRobotEyes(event) {
  if (!robot || !robotEyes.length) return;
  const head = robot.querySelector(".robot__head");
  if (!head) return;
  if (robot.classList.contains("eyes-closed")) return;
  const rect = head.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const maxOffset = 4;
  const dx = event.clientX - centerX;
  const dy = event.clientY - centerY;
  const distance = Math.max(Math.hypot(dx, dy), 1);
  const offsetX = (dx / distance) * maxOffset;
  const offsetY = (dy / distance) * maxOffset;
  if (robot.classList.contains("one-eye") && robotEyeRight) {
    robotEyeRight.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
    if (robotEyeLeft) robotEyeLeft.style.transform = "";
    return;
  }
  robotEyes.forEach((eye) => {
    eye.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
  });
}

function resetRobotEyes() {
  if (!robotEyes.length) return;
  robotEyes.forEach((eye) => {
    eye.style.transform = "";
  });
}

function showWelcomeOverlay() {
  const overlay = document.getElementById("admin-welcome-overlay");
  if (!overlay) return;
  overlay.classList.add("show");
  overlay.setAttribute("aria-hidden", "false");
  setTimeout(() => {
    overlay.classList.remove("show");
    overlay.setAttribute("aria-hidden", "true");
  }, 5000);
}

function initAdminSetup() {
  try {
    localStorage.removeItem(LEGACY_ADMIN_KEY);
  } catch (error) {
    // Ignore storage failures.
  }
  const existing = getStoredAdmin();
  if (!existing) {
    lockAdmin();
    openModal(setupModal);
    if (nameInput) {
      nameInput.focus();
    }
  } else {
    if (isAdminSessionActive()) {
      unlockAdmin();
    } else {
      lockAdmin();
      showLoginModal();
    }
  }
}

function showRecoverStep(step) {
  if (recoverStepEmail) recoverStepEmail.style.display = step === "email" ? "block" : "none";
  if (recoverStepOtp) recoverStepOtp.style.display = step === "otp" ? "block" : "none";
  if (recoverStepPassword) recoverStepPassword.style.display = step === "password" ? "block" : "none";
}

function openRecoverModal() {
  if (!recoverModal) return;
  recoveryOtp = "";
  if (recoverEmail) recoverEmail.value = "";
  if (recoverOtp) recoverOtp.value = "";
  if (recoverPassword) recoverPassword.value = "";
  if (recoverPasswordConfirm) recoverPasswordConfirm.value = "";
  if (recoverEmailStatus) recoverEmailStatus.textContent = "";
  if (recoverOtpStatus) recoverOtpStatus.textContent = "";
  if (recoverOtpHint) recoverOtpHint.textContent = "";
  if (recoverPasswordStatus) recoverPasswordStatus.textContent = "";
  showRecoverStep("email");
  openModal(recoverModal);
  if (recoverEmail) recoverEmail.focus();
}

function closeRecoverModal() {
  closeModal(recoverModal);
}

function handleSendOtp() {
  if (!recoverEmailStatus) return;
  const admin = getStoredAdmin();
  const email = (recoverEmail && recoverEmail.value.trim()) || "";
  if (!email) {
    recoverEmailStatus.textContent = "Email is required.";
    return;
  }
  if (!admin || !admin.email || admin.email.toLowerCase() !== email.toLowerCase()) {
    recoverEmailStatus.textContent = "Email not found.";
    return;
  }
  recoveryOtp = `${Math.floor(100000 + Math.random() * 900000)}`;
  if (recoverOtpHint) {
    recoverOtpHint.textContent = `Your OTP: ${recoveryOtp}`;
  }
  if (recoverEmailStatus) recoverEmailStatus.textContent = "";
  showRecoverStep("otp");
  if (recoverOtp) recoverOtp.focus();
}

function handleVerifyOtp() {
  if (!recoverOtpStatus) return;
  const entered = (recoverOtp && recoverOtp.value.trim()) || "";
  if (!entered || entered !== recoveryOtp) {
    recoverOtpStatus.textContent = "Invalid OTP.";
    return;
  }
  recoverOtpStatus.textContent = "";
  showRecoverStep("password");
  if (recoverPassword) recoverPassword.focus();
}

function handleSaveRecoveredPassword() {
  if (!recoverPasswordStatus) return;
  const admin = getStoredAdmin();
  if (!admin) {
    recoverPasswordStatus.textContent = "Admin account not found.";
    return;
  }
  const pwd = (recoverPassword && recoverPassword.value) || "";
  const confirm = (recoverPasswordConfirm && recoverPasswordConfirm.value) || "";
  if (!pwd || pwd.length < 4) {
    recoverPasswordStatus.textContent = "Password must be at least 4 characters.";
    return;
  }
  if (pwd !== confirm) {
    recoverPasswordStatus.textContent = "Passwords do not match.";
    return;
  }
  admin.password = pwd;
  setStoredAdmin(admin);
  upsertAdminList(admin);
  recoverPasswordStatus.textContent = "";
  closeRecoverModal();
  if (successTitle) successTitle.textContent = "Password updated";
  if (successMessage) successMessage.textContent = "Your admin password has been updated.";
  openModal(successModal);
}

if (setupSave) setupSave.addEventListener("click", handleSave);
if (setupClose) {
  setupClose.addEventListener("click", () => {
    if (adminLocked) return;
    closeModal(setupModal);
  });
}
if (successClose) successClose.addEventListener("click", () => closeModal(successModal));
if (successCta) successCta.addEventListener("click", () => closeModal(successModal));

if (setupModal) {
  setupModal.addEventListener("click", (event) => {
    if (event.target === setupModal) {
      if (adminLocked) return;
      closeModal(setupModal);
    }
  });
}

if (successModal) {
  successModal.addEventListener("click", (event) => {
    if (event.target === successModal) {
      closeModal(successModal);
    }
  });
}

if (loginSubmit) loginSubmit.addEventListener("click", handleLogin);
if (loginEmail) {
  loginEmail.addEventListener("focus", () => setRobotState("smile"));
}
if (loginPassword) {
  loginPassword.addEventListener("focus", () => setRobotState("eyes-closed"));
}
if (loginToggle && loginPassword) {
  loginToggle.addEventListener("click", () => {
    const isHidden = loginPassword.type === "password";
    loginPassword.type = isHidden ? "text" : "password";
    loginToggle.setAttribute("aria-label", isHidden ? "Hide password" : "Show password");
    setRobotState(isHidden ? "one-eye" : "eyes-closed");
  });
}
if (robot) {
  document.addEventListener("mousemove", trackRobotEyes);
  robot.addEventListener("mouseleave", resetRobotEyes);
}
if (loginClose) {
  loginClose.addEventListener("click", () => {
    if (adminLocked) return;
    closeModal(loginModal);
  });
}
if (loginModal) {
  loginModal.addEventListener("click", (event) => {
    if (event.target === loginModal) {
      if (adminLocked) return;
      closeModal(loginModal);
    }
  });
}

if (recoverClose) recoverClose.addEventListener("click", closeRecoverModal);
if (recoverSendOtp) recoverSendOtp.addEventListener("click", handleSendOtp);
if (recoverVerifyOtp) recoverVerifyOtp.addEventListener("click", handleVerifyOtp);
if (recoverSavePassword) recoverSavePassword.addEventListener("click", handleSaveRecoveredPassword);

if (recoverModal) {
  recoverModal.addEventListener("click", (event) => {
    if (event.target === recoverModal) {
      closeRecoverModal();
    }
  });
}

if (forgotBtn) forgotBtn.addEventListener("click", openRecoverModal);
if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    setAdminSession(false);
    if (typeof window.navigateTo === "function") {
      window.navigateTo("settings.html");
      return;
    }
    window.location.href = "settings.html";
  });
}

initAdminSetup();
if (adminAccountsOpen) {
  adminAccountsOpen.addEventListener("click", () => {
    if (typeof window.navigateTo === "function") {
      window.navigateTo("admin_accounts.html");
      return;
    }
    window.location.href = "admin_accounts.html";
  });
}
