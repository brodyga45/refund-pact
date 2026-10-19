/**
 ******************************************************************************
 * @file    main.cpp
 * @brief   HelloWorld LVGL PC simulator.
 *
 * Runs the app's real service and LVGL GUI processes against the SDK's mock
 * kernel (SDK/Libs/Source/Simulator): simulated sensors, a directory as the
 * file system, and the kernel's message protocol between the two processes.
 * The display is an SDL2 window showing the same ABGR2222 frames the watch
 * would receive.
 *
 * Compare with ../../TouchGFX-GUI/simulator/main.cpp: the kernel objects and
 * threads are the same; SDK::Simulator::LvglHost replaces the TouchGFX HAL.
 ******************************************************************************
 */

#include <thread>
#include <filesystem>
#include <cstdio>

#include "SDK/Kernel/KernelProviderGUI.hpp"
#include "SDK/Kernel/KernelProviderService.hpp"
#include "SDK/Port/LVGL/LvglPort.hpp"
#include "SDK/Simulator/App/AppMessageCore.hpp"
#include "SDK/Simulator/App/KernelMessageDispatcher.hpp"
#include "SDK/Simulator/Kernel/Kernel.hpp"
#include "SDK/Simulator/Kernel/Mock/Backlight.hpp"
#include "SDK/Simulator/Kernel/Mock/Buzzer.hpp"
#include "SDK/Simulator/Kernel/Mock/System.hpp"
#include "SDK/Simulator/Kernel/Mock/Vibro.hpp"
#include "SDK/Simulator/LVGL/LvglHost.hpp"

#include "Service.hpp"

#define LOG_MODULE_PRX      "main"
#define LOG_MODULE_LEVEL    LOG_LEVEL_INFO
#include "SDK/UnaLogger/Logger.h"

/// The GUI's entry hook, as on the watch (gui/src/GuiApp.cpp).
extern "C" void una_lvgl_app_init(void);

#ifdef RALLY_TRACE_FRAMES
static void snapshotFrame(lv_timer_t*)
{
    auto& port = SDK::LVGL::Port::GetInstance();
    static uint32_t previous = 0;
    if (previous == port.frameCount()) return;
    previous = port.frameCount();
    auto* file = std::fopen("rally-frame.ppm", "wb");
    if (!file) return;
    std::fprintf(file,"P6\n240 240\n255\n");
    const uint8_t* frame = port.frame();
    for (unsigned i=0;i<240*240;++i) {
        const uint8_t pixel=frame[i];
        const uint8_t rgb[] = {uint8_t((pixel&3)*85),uint8_t(((pixel>>2)&3)*85),uint8_t(((pixel>>4)&3)*85)};
        std::fwrite(rgb,1,3,file);
    }
    std::fclose(file);
}
#endif

int main(int, char**)
{
    // Keep all simulator writes in the OS temporary directory. In particular,
    // an unsigned macOS simulator must not access protected Documents on launch.
    // The SDK mock resolves its Output directory five levels above this cwd.
    std::error_code error;
    auto temporary = std::filesystem::temp_directory_path(error);
    if (error) return 2;
    auto runtime = temporary / "rally-slate-simulator" / "runtime" / "a/b/c/d/e";
    std::filesystem::create_directories(runtime, error);
    if (error) return 2;
    std::filesystem::current_path(runtime, error);
    if (error) return 2;
    std::freopen("rally-simulator.log", "w", stdout);
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    // Each process gets its own kernel view, as on the watch. The kernels are
    // declared before the message core on purpose: the core's destructor logs
    // the messages it drains, through the logger the service kernel owns, so
    // it has to go first when main() returns.
    SDK::Simulator::Mock::SystemService serviceSystem;
    SDK::Simulator::Kernel              serviceKernel("service");
    SDK::Simulator::Mock::SystemGUI     guiSystem;
    SDK::Simulator::Kernel              guiKernel("gui");

    // One message pool and the Service <-> GUI queues, as the kernel provides.
    SDK::App::MessageCore appMessageCore;
    SDK::App::DualAppComm& appComm = appMessageCore.getAppComm();

    serviceKernel.setIAppComm(appComm.getServiceComm());
    serviceKernel.setISystem(&serviceSystem);
    guiKernel.setIAppComm(appComm.getGuiComm());
    guiKernel.setISystem(&guiSystem);
    SDK::Simulator::KernelHolder::Create(guiKernel);

    Logger_init(serviceKernel.getKernel().log);
    SDK::KernelProviderService::CreateInstance(&serviceKernel.getKernel());
    SDK::KernelProviderGUI::CreateInstance(&guiKernel.getKernel());

    // The service process.
    Service service(SDK::KernelProviderService::GetInstance().getKernel());

    // The kernel side: answers both processes' requests and runs the sensors.
    SDK::Simulator::Mock::Backlight   backlight;
    SDK::Simulator::Mock::Buzzer      buzzer;
    SDK::Simulator::Mock::Vibro       vibro;
    SDK::App::KernelMessageDispatcher dispatcher(appComm, appComm.getMsgManager(), vibro, backlight, buzzer);

    // The display, ticks and buttons the kernel would supply to the GUI.
    SDK::Simulator::LvglHost::Options options;
    options.title = "Rally Slate - simulator";
    options.scale = 2;
    SDK::Simulator::LvglHost host(appComm, serviceKernel.getKernel(), options);
    if (!host.init()) {
        return 1;
    }

    std::thread serviceThread(&Service::run, &service);
    std::thread dispatcherThread(&SDK::App::KernelMessageDispatcher::run, &dispatcher);

    // The GUI process, exactly as EntryPoint/LVGL/main.cpp runs it on the watch.
    SDK::LVGL::Port& port = SDK::LVGL::Port::GetInstance();
    port.init();
    una_lvgl_app_init();
#ifdef RALLY_TRACE_FRAMES
    lv_timer_create(&snapshotFrame,500,nullptr);
#endif

    host.start();
    host.run();
    host.shutdown();

    serviceThread.join();
    dispatcherThread.join();

    LOG_INFO("Simulator finished\n");
    return 0;
}
