// Голосій (Holosii) — оболонка для Windows (як mac/main.swift для macOS).
// Запускає server.py (якщо він ще не працює), показує сторінку у власному вікні (WebView2)
// і при закритті вікна зупиняє сервер разом з агентом. Якщо сервер запустили окремо — не чіпає його.
//
// Сервер зупиняється так: оболонка тримає відкритим його stdin і закриває його при виході
// (server.py --stdin-stop); якщо за 6 с не вийшов — дерево процесів завершується примусово.
// Сервер і все, що він запустив (Claude Code, ffmpeg), — в Job Object з KILL_ON_JOB_CLOSE,
// тож навіть після аварійного виходу оболонки нічого не лишається працювати у фоні.
using System.Diagnostics;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace Holosii;

static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}

sealed class MainForm : Form
{
    readonly WebView2 web = new() { Dock = DockStyle.Fill };
    readonly HttpClient http = new() { Timeout = TimeSpan.FromMilliseconds(800) };
    readonly string dir = ServerDir();
    readonly int port;
    readonly Uri baseUri;
    Process? server;
    StreamWriter? log;
    bool closing;
    static readonly string AppData = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Holosii");

    public MainForm()
    {
        port = ServerPort(dir);
        baseUri = new Uri($"http://localhost:{port}/");
        Text = "Голосій";
        MinimumSize = new Size(900, 560);
        Size = new Size(1320, 840);
        StartPosition = FormStartPosition.CenterScreen;
        using (var s = typeof(MainForm).Assembly.GetManifestResourceStream("Holosii.ico"))
            if (s != null) Icon = new Icon(s);
        LoadBounds();
        Controls.Add(web);
        Load += async (_, _) => await Init();
        FormClosing += (_, _) => { closing = true; SaveBounds(); StopServer(); };
    }

    // ---------- тека з server.py і порт ----------

    // HOLOSII_SERVER_DIR → тека Holosii.exe → її батьківські теки (щоб працювало й з win\bin\...)
    static string ServerDir()
    {
        var env = Environment.GetEnvironmentVariable("HOLOSII_SERVER_DIR");
        if (!string.IsNullOrEmpty(env) && File.Exists(Path.Combine(env, "server.py"))) return env;
        var d = new DirectoryInfo(AppContext.BaseDirectory);
        for (var x = d; x != null; x = x.Parent)
            if (File.Exists(Path.Combine(x.FullName, "server.py"))) return x.FullName;
        return d.FullName;
    }

    // Порт: змінна PORT → "port" у settings.json поруч із server.py → 8765 (так само, як у server.py)
    static int ServerPort(string dir)
    {
        if (int.TryParse(Environment.GetEnvironmentVariable("PORT"), out var p)) return p;
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(Path.Combine(dir, "settings.json")));
            if (doc.RootElement.TryGetProperty("port", out var v) && v.TryGetInt32(out p)) return p;
        }
        catch (Exception) { }
        return 8765;
    }

    // ---------- WebView2 ----------

    async Task Init()
    {
        try
        {
            var env = await CoreWebView2Environment.CreateAsync(null, Path.Combine(AppData, "WebView2"));
            await web.EnsureCoreWebView2Async(env);
        }
        catch (Exception e)
        {
            MessageBox.Show("Не вдалося запустити WebView2. Встановіть Microsoft Edge WebView2 Runtime:\n" +
                            "https://developer.microsoft.com/microsoft-edge/webview2/\n\n" + e.Message,
                            "Голосій", MessageBoxButtons.OK, MessageBoxIcon.Error);
            Close();
            return;
        }
        var core = web.CoreWebView2;
        core.Settings.IsStatusBarEnabled = false;
        core.Settings.AreDevToolsEnabled = true;
        core.DocumentTitleChanged += (_, _) => Text = string.IsNullOrWhiteSpace(core.DocumentTitle) ? "Голосій" : core.DocumentTitle;

        // мікрофон для диктування (запис у сторінці → Whisper на сервері) — лише для localhost
        core.PermissionRequested += (_, e) =>
        {
            var local = IsLocal(e.Uri);
            if (e.PermissionKind == CoreWebView2PermissionKind.Microphone)
                e.State = local ? CoreWebView2PermissionState.Allow : CoreWebView2PermissionState.Deny;
            else if (e.PermissionKind == CoreWebView2PermissionKind.ClipboardRead && local)
                e.State = CoreWebView2PermissionState.Allow;
        };
        // target=_blank і зовнішні посилання — у звичайному браузері
        core.NewWindowRequested += (_, e) => { e.Handled = true; OpenExternal(e.Uri); };
        core.NavigationStarting += (_, e) =>
        {
            var u = e.Uri ?? "";
            if (u.StartsWith("holosii:", StringComparison.OrdinalIgnoreCase))
            {
                e.Cancel = true;
                BeginInvoke(new Action(async () => { ShowMessage("Запускаю Голосій…"); await Start(); }));
                return;
            }
            if (IsLocal(u) || u.StartsWith("about:") || u.StartsWith("data:")) return;
            e.Cancel = true;
            OpenExternal(u);
        };
        ShowMessage("Запускаю Голосій…");
        await Start();
    }

    static bool IsLocal(string uri) =>
        Uri.TryCreate(uri, UriKind.Absolute, out var u) &&
        (u.Scheme == "http" || u.Scheme == "https") &&
        (u.Host == "localhost" || u.Host == "127.0.0.1" || u.Host == "[::1]");

    static void OpenExternal(string uri)
    {
        if (!Uri.TryCreate(uri, UriKind.Absolute, out var u) || (u.Scheme != "http" && u.Scheme != "https" && u.Scheme != "mailto"))
            return;
        try { Process.Start(new ProcessStartInfo(u.AbsoluteUri) { UseShellExecute = true }); } catch (Exception) { }
    }

    void ShowMessage(string html)
    {
        if (web.CoreWebView2 == null) return;
        web.CoreWebView2.NavigateToString(
            "<html><body style=\"margin:0;height:100vh;display:grid;place-items:center;font:14px 'Segoe UI',sans-serif;" +
            "color:#888;text-align:center\"><div>" + html + "</div></body></html>");
    }

    // ---------- сервер ----------

    async Task<bool> Ping()
    {
        try { return (await http.GetAsync(new Uri(baseUri, "api/state"))).IsSuccessStatusCode; }
        catch (Exception) { return false; }
    }

    async Task Start()
    {
        if (await Ping()) { web.CoreWebView2.Navigate(baseUri.AbsoluteUri); return; }
        if (!LaunchServer()) return;
        for (var i = 0; i < 80 && server != null; i++)
        {
            if (await Ping()) { web.CoreWebView2.Navigate(baseUri.AbsoluteUri); return; }
            await Task.Delay(250);
        }
        if (server != null) ShowMessage("Сервер не відповідає. Журнал: logs\\app_server.log");
    }

    // Python: HOLOSII_PYTHON → py.exe (лаунчер python.org) → python.exe у PATH (не заглушка з Microsoft Store)
    static (string exe, string[] pre)? FindPython()
    {
        var env = Environment.GetEnvironmentVariable("HOLOSII_PYTHON");
        if (!string.IsNullOrEmpty(env) && File.Exists(env)) return (env, Array.Empty<string>());
        var path = (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';', StringSplitOptions.RemoveEmptyEntries);
        string? Find(string name) => path.Select(d => Path.Combine(d.Trim('"'), name))
            .FirstOrDefault(f => File.Exists(f) && !f.Contains("\\WindowsApps\\", StringComparison.OrdinalIgnoreCase));
        var py = Find("py.exe");
        if (py != null) return (py, new[] { "-3" });
        var python = Find("python.exe");
        return python != null ? (python, Array.Empty<string>()) : null;
    }

    bool LaunchServer()
    {
        if (!File.Exists(Path.Combine(dir, "server.py")))
        {
            ShowMessage("Не знайдено server.py у теці:<br>" + Html(dir));
            return false;
        }
        var py = FindPython();
        if (py == null)
        {
            ShowMessage("Не знайдено Python 3. Встановіть його з python.org (з «py launcher») і запустіть Голосій знову.");
            return false;
        }
        var logs = Path.Combine(dir, "logs");
        Directory.CreateDirectory(logs);
        log?.Dispose();
        log = new StreamWriter(Path.Combine(logs, "app_server.log"), false, new UTF8Encoding(false)) { AutoFlush = true };

        var psi = new ProcessStartInfo(py.Value.exe)
        {
            WorkingDirectory = dir,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardInput = true,          // закриємо при виході → server.py зупиниться (--stdin-stop)
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (var a in py.Value.pre) psi.ArgumentList.Add(a);
        foreach (var a in new[] { "-X", "utf8", "server.py", "--no-open", "--stdin-stop" }) psi.ArgumentList.Add(a);
        psi.Environment["PYTHONUNBUFFERED"] = "1";
        psi.Environment["PYTHONUTF8"] = "1";       // і для скриптів, які запускає агент
        var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
        p.OutputDataReceived += (_, e) => { if (e.Data != null) WriteLog(e.Data); };
        p.ErrorDataReceived += (_, e) => { if (e.Data != null) WriteLog(e.Data); };
        p.Exited += (_, _) =>
        {
            if (closing || IsDisposed) return;
            try
            {
                BeginInvoke(new Action(() =>
                {
                    if (closing || server != p) return;
                    server = null;
                    ShowMessage($"Сервер Голосія зупинився (код {p.ExitCode}).<br>Журнал: logs\\app_server.log<br><br>" +
                                "<a href='holosii:restart'>Запустити знову</a>");
                }));
            }
            catch (InvalidOperationException) { }  // вікно вже закрите
        };
        try { p.Start(); }
        catch (Exception e)
        {
            ShowMessage("Не вдалося запустити Python: " + Html(e.Message));
            return false;
        }
        Job.Add(p);
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
        server = p;
        return true;
    }

    void WriteLog(string line)
    {
        try { lock (this) log?.WriteLine(line); } catch (Exception) { }
    }

    void StopServer()
    {
        var p = server;
        server = null;
        if (p == null) return;
        try
        {
            if (p.HasExited) return;
            p.StandardInput.Close();               // server.py зупиняє агента й виходить
            if (!p.WaitForExit(6000)) p.Kill(entireProcessTree: true);
        }
        catch (Exception) { }
    }

    static string Html(string s) => System.Net.WebUtility.HtmlEncode(s);

    // ---------- розмір і місце вікна між запусками ----------

    static string BoundsFile => Path.Combine(AppData, "window.txt");

    void LoadBounds()
    {
        try
        {
            var v = File.ReadAllText(BoundsFile).Split(',').Select(int.Parse).ToArray();
            var r = new Rectangle(v[0], v[1], v[2], v[3]);
            if (Screen.AllScreens.Any(s => s.WorkingArea.IntersectsWith(r)))
            {
                StartPosition = FormStartPosition.Manual;
                Bounds = r;
                if (v.Length > 4 && v[4] == 1) WindowState = FormWindowState.Maximized;
            }
        }
        catch (Exception) { }
    }

    void SaveBounds()
    {
        try
        {
            var r = WindowState == FormWindowState.Normal ? Bounds : RestoreBounds;
            Directory.CreateDirectory(AppData);
            File.WriteAllText(BoundsFile, $"{r.X},{r.Y},{r.Width},{r.Height},{(WindowState == FormWindowState.Maximized ? 1 : 0)}");
        }
        catch (Exception) { }
    }
}

// Job Object: коли Holosii.exe завершується (будь-як), Windows завершує сервер і все, що він запустив.
static class Job
{
    static readonly IntPtr handle = Create();

    static IntPtr Create()
    {
        var h = CreateJobObject(IntPtr.Zero, null);
        if (h == IntPtr.Zero) return h;
        var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
        info.BasicLimitInformation.LimitFlags = 0x2000;   // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        SetInformationJobObject(h, 9, ref info, (uint)Marshal.SizeOf<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>());
        return h;
    }

    public static void Add(Process p)
    {
        if (handle != IntPtr.Zero)
            try { AssignProcessToJobObject(handle, p.Handle); } catch (Exception) { }
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr CreateJobObject(IntPtr attributes, string? name);

    [DllImport("kernel32.dll")]
    static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION info, uint size);

    [DllImport("kernel32.dll")]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct IO_COUNTERS
    {
        public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
        public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }
}
