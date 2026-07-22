import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate {
  private var screenshotChannel: FlutterMethodChannel?

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    GeneratedPluginRegistrant.register(with: self)
    let ok = super.application(application, didFinishLaunchingWithOptions: launchOptions)

    if let controller = window?.rootViewController as? FlutterViewController {
      screenshotChannel = FlutterMethodChannel(
        name: "bhukhadan/screenshot_audit",
        binaryMessenger: controller.binaryMessenger
      )
    }

    NotificationCenter.default.addObserver(
      self,
      selector: #selector(userDidTakeScreenshot),
      name: UIApplication.userDidTakeScreenshotNotification,
      object: nil
    )

    return ok
  }

  @objc private func userDidTakeScreenshot() {
    // iOS can detect screenshots; blocking is not available like Android FLAG_SECURE.
    screenshotChannel?.invokeMethod("onScreenshot", arguments: nil)
  }
}
