const { app, BrowserWindow } = require('electron');
const { exec } = require('child_process');
const path = require('path');

let pyProcess = null;

function createWindow() {
  // 1. ප්‍රධාන Window එක නිර්මාණය කිරීම
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    backgroundColor: '#000000', // PRISPOINT තේමාවට ගැළපෙන ලෙස
    title: "PRISPOINT VCS",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // 2. මෙහෙයුම් පද්ධතිය අනුව Backend එක තෝරාගැනීම
  let backendPath;
  if (process.platform === 'win32') {
    // Windows සඳහා
    backendPath = path.join(__dirname, 'dist', 'app.exe');
  } else {
    // Linux සඳහා
    backendPath = path.join(__dirname, 'dist', 'app');
  }

  // 3. Backend එක (Flask Server) පණ ගැන්වීම
  console.log("Starting backend at: " + backendPath);
  pyProcess = exec(backendPath, (err) => {
    if (err) {
      console.error("Failed to start backend:", err);
    }
  });

  // 4. Server එක පණ ගැන්වෙන තෙක් තත්පර 3ක් රැඳී සිට වෙබ් අඩවිය Load කිරීම
  // ඔබේ සර්වර් එකේ වේගය අනුව මෙය තත්පර 5 (5000) දක්වා වැඩි කළ හැක
  setTimeout(() => {
    win.loadURL('http://127.0.0.1:5001');
    
    // වෙබ් අඩවිය load නොවන්නේ නම් නැවත උත්සාහ කිරීමට
    win.webContents.on('did-fail-load', () => {
      console.log("Re-trying to connect...");
      setTimeout(() => win.loadURL('http://127.0.0.1:5001'), 2000);
    });
  }, 3000);
}

// Linux (Kali) වල ඇතිවිය හැකි Sandbox ගැටළු මඟහරවා ගැනීමට
if (process.platform === 'linux') {
  app.commandLine.appendSwitch('no-sandbox');
}

// App එක සූදානම් වූ පසු Window එක පෙන්වීම
app.whenReady().then(createWindow);

// සියලු Window වැසූ පසු Python process එක නතර කිරීම
app.on('window-all-closed', () => {
  if (pyProcess != null) {
    // Windows වලදී taskkill භාවිතා කිරීම වඩාත් සාර්ථකයි
    if (process.platform === 'win32') {
      exec(`taskkill /pid ${pyProcess.pid} /f /t`);
    } else {
      pyProcess.kill();
    }
  }
  if (process.platform !== 'darwin') app.quit();
});
