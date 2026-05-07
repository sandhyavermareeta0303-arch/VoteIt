using Microsoft.Win32;
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Windows.Forms;

namespace VoteItInstaller
{
    internal static class Program
    {
        private const string AppName = "VoteIt";
        private const string AppVersion = "0.1.0";

        [STAThread]
        private static int Main()
        {
            Application.EnableVisualStyles();

            try
            {
                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                string programsDir = Path.Combine(localAppData, "Programs");
                string installDir = Path.Combine(programsDir, AppName);
                string dataDir = Path.Combine(localAppData, AppName);
                string exePath = Path.Combine(installDir, "VoteIt.exe");
                string uninstallPath = Path.Combine(installDir, "uninstall_voteit.ps1");
                string startMenuDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "Microsoft",
                    "Windows",
                    "Start Menu",
                    "Programs",
                    AppName
                );
                string desktopShortcut = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                    "VoteIt.lnk"
                );

                AssertUnderPath(installDir, programsDir);
                Directory.CreateDirectory(programsDir);

                string tempZip = Path.Combine(Path.GetTempPath(), "VoteIt_app_" + Guid.NewGuid().ToString("N") + ".zip");
                try
                {
                    WriteResourceToFile("VoteIt_app.zip", tempZip);

                    if (Directory.Exists(installDir))
                    {
                        Directory.Delete(installDir, true);
                    }

                    Directory.CreateDirectory(installDir);
                    ZipFile.ExtractToDirectory(tempZip, installDir);
                    WriteResourceToFile("uninstall_voteit.ps1", uninstallPath);

                    Directory.CreateDirectory(dataDir);
                    Directory.CreateDirectory(startMenuDir);

                    CreateShortcut(desktopShortcut, exePath, "", installDir);
                    CreateShortcut(Path.Combine(startMenuDir, "VoteIt.lnk"), exePath, "", installDir);
                    CreateShortcut(
                        Path.Combine(startMenuDir, "Uninstall VoteIt.lnk"),
                        "powershell.exe",
                        "-NoProfile -ExecutionPolicy Bypass -File \"" + uninstallPath + "\"",
                        installDir
                    );

                    RegisterUninstallEntry(installDir, exePath, uninstallPath);

                    Process.Start(new ProcessStartInfo
                    {
                        FileName = exePath,
                        WorkingDirectory = installDir,
                        UseShellExecute = true
                    });

                    MessageBox.Show(
                        "VoteIt installed successfully.",
                        "VoteIt Setup",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Information
                    );
                    return 0;
                }
                finally
                {
                    if (File.Exists(tempZip))
                    {
                        File.Delete(tempZip);
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "VoteIt installation failed:\n\n" + ex.Message,
                    "VoteIt Setup",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 1;
            }
        }

        private static void RegisterUninstallEntry(string installDir, string exePath, string uninstallPath)
        {
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\VoteIt"))
            {
                if (key == null)
                {
                    return;
                }

                key.SetValue("DisplayName", AppName);
                key.SetValue("DisplayVersion", AppVersion);
                key.SetValue("Publisher", AppName);
                key.SetValue("InstallLocation", installDir);
                key.SetValue("DisplayIcon", exePath);
                key.SetValue("UninstallString", "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"" + uninstallPath + "\"");
                key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
            }
        }

        private static void WriteResourceToFile(string resourceName, string targetPath)
        {
            Assembly assembly = Assembly.GetExecutingAssembly();
            string match = null;
            foreach (string name in assembly.GetManifestResourceNames())
            {
                if (name.EndsWith(resourceName, StringComparison.OrdinalIgnoreCase))
                {
                    match = name;
                    break;
                }
            }

            if (match == null)
            {
                throw new FileNotFoundException("Embedded installer resource not found: " + resourceName);
            }

            using (Stream input = assembly.GetManifestResourceStream(match))
            using (FileStream output = File.Create(targetPath))
            {
                if (input == null)
                {
                    throw new FileNotFoundException("Embedded installer resource could not be opened: " + resourceName);
                }
                input.CopyTo(output);
            }
        }

        private static void CreateShortcut(string shortcutPath, string targetPath, string arguments, string workingDirectory)
        {
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            if (shellType == null)
            {
                return;
            }

            object shell = Activator.CreateInstance(shellType);
            object shortcut = shellType.InvokeMember(
                "CreateShortcut",
                BindingFlags.InvokeMethod,
                null,
                shell,
                new object[] { shortcutPath }
            );

            Type shortcutType = shortcut.GetType();
            shortcutType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
            shortcutType.InvokeMember("Arguments", BindingFlags.SetProperty, null, shortcut, new object[] { arguments });
            shortcutType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { workingDirectory });
            shortcutType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
            shortcutType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
        }

        private static void AssertUnderPath(string path, string parent)
        {
            string fullPath = Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string fullParent = Path.GetFullPath(parent).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
            if (!fullPath.StartsWith(fullParent, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException("Refusing to install outside expected location: " + fullPath);
            }
        }
    }
}
