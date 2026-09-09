using System;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Pipes;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using EasyHook;
using HarmonyLib;

namespace TerrariaAutoFisher.Injector
{
    internal static class Program
    {
        private static int Main(string[] args)
        {
            Console.OutputEncoding = new UTF8Encoding(false);
            if (args.Length == 1 && args[0] == "hold")
            {
                Thread.Sleep(Timeout.Infinite);
                return 0;
            }
            if (args.Length == 1 && args[0] == "self-test")
                return RunSelfTest();
            if (args.Length != 5 || args[0] != "attach" ||
                !int.TryParse(args[1], NumberStyles.None, CultureInfo.InvariantCulture, out var targetPid) ||
                !int.TryParse(args[3], NumberStyles.None, CultureInfo.InvariantCulture, out var ownerPid))
            {
                Console.Error.WriteLine(
                    "Usage: TerrariaAutoFisher.Injector.exe attach <terraria-pid> <pipe-name> <owner-pid> <status-file>");
                return 2;
            }

            try
            {
                using (var target = Process.GetProcessById(targetPid))
                {
                    if (!string.Equals(target.ProcessName, "Terraria", StringComparison.OrdinalIgnoreCase))
                        throw new InvalidOperationException("目标进程不是 Terraria.exe");
                }

                InjectPayload(targetPid, args[2], ownerPid, args[4]);
                Console.WriteLine("INJECTED");
                return 0;
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine(exception);
                return 1;
            }
        }

        private static void InjectPayload(
            int targetPid, string pipeName, int ownerPid, string statusPath)
        {
            var payloadPath = Assembly.GetExecutingAssembly().Location;
            var payloadDirectory = Path.GetDirectoryName(payloadPath);
            Config.DependencyPath = payloadDirectory;
            Config.HelperLibraryLocation = payloadDirectory;
            RemoteHooking.Inject(
                targetPid,
                InjectionOptions.DoNotRequireStrongName | InjectionOptions.NoService,
                payloadPath,
                null,
                pipeName,
                ownerPid,
                statusPath);
        }

        private static int RunSelfTest()
        {
            Process target = null;
            var pipeName = "TerrariaAutoFisher_SelfTest_" + Guid.NewGuid().ToString("N");
            var statusPath = Path.Combine(
                Path.GetTempPath(), pipeName + ".status");
            try
            {
                target = Process.Start(new ProcessStartInfo(
                    Assembly.GetExecutingAssembly().Location, "hold")
                {
                    UseShellExecute = false,
                    CreateNoWindow = true
                });
                Thread.Sleep(250);
                InjectPayload(target.Id, pipeName, Process.GetCurrentProcess().Id, statusPath);
                var response = SendPipeCommand(pipeName, "PING");
                if (!response.StartsWith("ERROR ", StringComparison.Ordinal))
                    throw new InvalidOperationException(
                        "自检目标应报告缺少 Terraria 程序集，实际响应：" + response);
                if (SendPipeCommand(pipeName, "DISABLE") != "DISABLED")
                    throw new InvalidOperationException("DISABLE 命令自检失败");
                var secondResponse = SendPipeCommand(pipeName, "PING");
                if (!secondResponse.StartsWith("ERROR ", StringComparison.Ordinal))
                    throw new InvalidOperationException("持久管道复用自检失败");
                SendPipeCommand(pipeName, "STOP");
                Console.WriteLine("SELF_TEST_OK");
                return 0;
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine(exception);
                if (File.Exists(statusPath))
                    Console.Error.WriteLine(File.ReadAllText(statusPath));
                return 1;
            }
            finally
            {
                try
                {
                    if (target != null && !target.HasExited)
                        target.Kill();
                }
                catch
                {
                }
                try
                {
                    File.Delete(statusPath);
                }
                catch
                {
                }
                target?.Dispose();
            }
        }

        private static string SendPipeCommand(string pipeName, string command)
        {
            using (var pipe = new NamedPipeClientStream(
                ".", pipeName, PipeDirection.InOut))
            {
                pipe.Connect(5000);
                using (var reader = new StreamReader(pipe))
                using (var writer = new StreamWriter(pipe) { AutoFlush = true })
                {
                    writer.WriteLine(command);
                    return reader.ReadLine() ?? string.Empty;
                }
            }
        }
    }

    public sealed class InjectedEntryPoint : IEntryPoint
    {
        private readonly string pipeName;
        private readonly int ownerPid;
        private readonly string statusPath;

        public InjectedEntryPoint(
            RemoteHooking.IContext context, string pipeName, int ownerPid, string statusPath)
        {
            this.pipeName = pipeName;
            this.ownerPid = ownerPid;
            this.statusPath = statusPath;
            WriteStatus("ENTRY_CONSTRUCTED");
        }

        public void Run(
            RemoteHooking.IContext context, string pipeName, int ownerPid, string statusPath)
        {
            DefaultDomainBootstrap bootstrap = null;
            try
            {
                WriteStatus("ENTRY_RUNNING");
                var defaultDomain = ClrHost.GetDefaultAppDomain();
                WriteStatus("DEFAULT_DOMAIN_FOUND");
                bootstrap = (DefaultDomainBootstrap)defaultDomain.CreateInstanceFromAndUnwrap(
                    Assembly.GetExecutingAssembly().Location,
                    typeof(DefaultDomainBootstrap).FullName,
                    false,
                    BindingFlags.Public | BindingFlags.Instance,
                    null,
                    new object[] { this.pipeName, this.ownerPid, this.statusPath },
                    CultureInfo.InvariantCulture,
                    null);
                WriteStatus("BOOTSTRAP_CREATED");
                RemoteHooking.WakeUpProcess();
                while (bootstrap.IsRunning)
                    Thread.Sleep(250);
            }
            catch (Exception exception)
            {
                WriteStatus("ENTRY_ERROR" + Environment.NewLine + exception);
            }
            finally
            {
                bootstrap?.Stop();
            }
        }

        private void WriteStatus(string status)
        {
            try
            {
                File.WriteAllText(statusPath, status, new UTF8Encoding(false));
            }
            catch
            {
            }
        }

    }

    public sealed class DefaultDomainBootstrap : MarshalByRefObject
    {
        private const string HarmonyId = "terraria.autofisher.delay-use-item";
        private const string ProtocolVersion = "1.0.2";
        private readonly Harmony harmony;
        private readonly string initializationError;
        private readonly string pipeName;
        private readonly string statusPath;
        private readonly Thread serverThread;
        private volatile bool running = true;

        public DefaultDomainBootstrap(string pipeName, int ownerPid, string statusPath)
        {
            this.pipeName = pipeName;
            this.statusPath = statusPath;
            try
            {
                harmony = new Harmony(HarmonyId);
                RuntimePatch.Initialize(harmony);
            }
            catch (Exception exception)
            {
                initializationError = FormatError(exception);
                WriteStatus("PATCH_ERROR" + Environment.NewLine + exception);
            }
            serverThread = new Thread(RunPipeServer)
            {
                IsBackground = true,
                Name = "TerrariaAutoFisherPipe"
            };
            serverThread.Start();
        }

        public bool IsRunning => running;

        public void Stop()
        {
            if (!running)
                return;
            running = false;
            PulseGate.Disable();
            harmony?.UnpatchAll(HarmonyId);
        }

        public override object InitializeLifetimeService()
        {
            return null;
        }

        private void RunPipeServer()
        {
            try
            {
                while (running)
                {
                    using (var pipe = new NamedPipeServerStream(
                        pipeName,
                        PipeDirection.InOut,
                        1,
                        PipeTransmissionMode.Byte,
                        PipeOptions.Asynchronous))
                    {
                        WriteStatus("PIPE_LISTENING");
                        var connection = pipe.WaitForConnectionAsync();
                        while (!connection.Wait(250))
                        {
                            if (!running)
                                return;
                        }

                        using (var reader = new StreamReader(pipe))
                        using (var writer = new StreamWriter(pipe) { AutoFlush = true })
                        {
                            var command = reader.ReadLine() ?? string.Empty;
                            if (command == "PING")
                            {
                                writer.WriteLine(initializationError == null
                                    ? "READY " + ProtocolVersion
                                    : "ERROR " + initializationError);
                            }
                            else if (command == "DISABLE")
                            {
                                PulseGate.Disable();
                                writer.WriteLine("DISABLED");
                            }
                            else if (command == "STOP")
                            {
                                writer.WriteLine("STOPPING");
                                return;
                            }
                            else if (command.StartsWith("PULSE ", StringComparison.Ordinal) &&
                                     initializationError == null &&
                                     int.TryParse(command.Substring(6), NumberStyles.None,
                                         CultureInfo.InvariantCulture, out var milliseconds))
                            {
                                PulseGate.EnableFor(milliseconds);
                                writer.WriteLine("PULSED");
                            }
                            else
                            {
                                writer.WriteLine("ERROR");
                            }
                        }
                    }
                }
            }
            catch (Exception exception)
            {
                WriteStatus("PIPE_ERROR" + Environment.NewLine + exception);
            }
            finally
            {
                Stop();
            }
        }

        private static string FormatError(Exception exception)
        {
            var root = exception;
            while (root.InnerException != null)
                root = root.InnerException;
            return (root.GetType().Name + ": " + root.Message)
                .Replace('\r', ' ')
                .Replace('\n', ' ');
        }

        private void WriteStatus(string status)
        {
            try
            {
                File.WriteAllText(statusPath, status, new UTF8Encoding(false));
            }
            catch
            {
            }
        }
    }

    internal static class ClrHost
    {
        private static readonly Guid ClsidCorRuntimeHost =
            new Guid("CB2F6723-AB3A-11D2-9C40-00C04FA30A3E");
        private static readonly Guid IidCorRuntimeHost =
            new Guid("CB2F6722-AB3A-11D2-9C40-00C04FA30A3E");

        public static AppDomain GetDefaultAppDomain()
        {
            var hostObject = RuntimeEnvironment.GetRuntimeInterfaceAsObject(
                ClsidCorRuntimeHost, IidCorRuntimeHost);
            var host = (ICorRuntimeHost)hostObject;
            var result = host.GetDefaultDomain(out var domainObject);
            if (result < 0)
                Marshal.ThrowExceptionForHR(result);
            return (AppDomain)domainObject;
        }

        [ComImport]
        [Guid("CB2F6722-AB3A-11D2-9C40-00C04FA30A3E")]
        [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface ICorRuntimeHost
        {
            [PreserveSig] int CreateLogicalThreadState();
            [PreserveSig] int DeleteLogicalThreadState();
            [PreserveSig] int SwitchInLogicalThreadState(IntPtr fiberCookie);
            [PreserveSig] int SwitchOutLogicalThreadState(out IntPtr fiberCookie);
            [PreserveSig] int LocksHeldByLogicalThread(out int count);
            [PreserveSig] int MapFile(IntPtr file, out IntPtr mapAddress);
            [PreserveSig] int GetConfiguration(out IntPtr configuration);
            [PreserveSig] int Start();
            [PreserveSig] int Stop();
            [PreserveSig] int CreateDomain(
                [MarshalAs(UnmanagedType.LPWStr)] string friendlyName,
                [MarshalAs(UnmanagedType.IUnknown)] object identityArray,
                [MarshalAs(UnmanagedType.IUnknown)] out object appDomain);
            [PreserveSig] int GetDefaultDomain(
                [MarshalAs(UnmanagedType.IUnknown)] out object appDomain);
        }
    }

    internal static class PulseGate
    {
        private static long activeUntil;

        public static bool IsActive => Stopwatch.GetTimestamp() < Interlocked.Read(ref activeUntil);

        public static void EnableFor(int milliseconds)
        {
            var bounded = Math.Max(50, Math.Min(milliseconds, 2000));
            var duration = (long)(Stopwatch.Frequency * (bounded / 1000.0));
            Interlocked.Exchange(ref activeUntil, Stopwatch.GetTimestamp() + duration);
        }

        public static void Disable()
        {
            Interlocked.Exchange(ref activeUntil, 0);
        }
    }

    internal static class RuntimePatch
    {
        private static FieldInfo delayUseItemField;
        private static FieldInfo controlUseItemField;
        private static PropertyInfo mouseLeftProperty;
        private static PropertyInfo localPlayerProperty;

        public static void Initialize(Harmony harmony)
        {
            var terraria = AppDomain.CurrentDomain.GetAssemblies()
                .FirstOrDefault(assembly => assembly.GetName().Name == "Terraria")
                ?? throw new InvalidOperationException("Terraria 程序集尚未加载");
            var triggersType = terraria.GetType("Terraria.GameInput.TriggersSet", true);
            var playerType = terraria.GetType("Terraria.Player", true);
            var mainType = terraria.GetType("Terraria.Main", true);

            delayUseItemField = playerType.GetField("delayUseItem", BindingFlags.Instance | BindingFlags.Public)
                ?? throw new MissingFieldException(playerType.FullName, "delayUseItem");
            controlUseItemField = playerType.GetField("controlUseItem", BindingFlags.Instance | BindingFlags.Public)
                ?? throw new MissingFieldException(playerType.FullName, "controlUseItem");
            mouseLeftProperty = triggersType.GetProperty("MouseLeft", BindingFlags.Instance | BindingFlags.Public)
                ?? throw new MissingMemberException(triggersType.FullName, "MouseLeft");
            localPlayerProperty = mainType.GetProperty("LocalPlayer", BindingFlags.Static | BindingFlags.Public)
                ?? throw new MissingMemberException(mainType.FullName, "LocalPlayer");

            var original = triggersType.GetMethod(
                "CopyInto",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                null,
                new[] { playerType },
                null) ?? throw new MissingMethodException(triggersType.FullName, "CopyInto");
            var postfix = typeof(RuntimePatch).GetMethod(
                nameof(CopyIntoPostfix), BindingFlags.Static | BindingFlags.NonPublic);
            harmony.Patch(original, postfix: new HarmonyMethod(postfix));
        }

        private static void CopyIntoPostfix(object __instance, object __0)
        {
            if (!PulseGate.IsActive || !(bool)mouseLeftProperty.GetValue(__instance, null))
                return;

            var localPlayer = localPlayerProperty.GetValue(null, null);
            if (!ReferenceEquals(localPlayer, __0))
                return;

            delayUseItemField.SetValue(__0, false);
            controlUseItemField.SetValue(__0, true);
        }
    }
}
