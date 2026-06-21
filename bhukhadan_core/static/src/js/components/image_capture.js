/** @odoo-module **/

import { isMobileOS } from "@web/core/browser/feature_detection";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { url } from "@web/core/utils/urls";
import { isBinarySize } from "@web/core/utils/binary";
import { rpc } from "@web/core/network/rpc";
import { FileUploader } from "@web/views/fields/file_handler";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, onWillUpdateProps, useRef } from "@odoo/owl";
const { DateTime } = luxon;
export const fileTypeMagicWordMap = {
    "/": "jpg",
    R: "gif",
    i: "png",
    P: "svg+xml",
};

const placeholder = "/web/static/img/placeholder.png";
export function imageCacheKey(value) {
    if (value instanceof DateTime) {
        return value.ts;
    }
    return "";
}
class imageCapture extends Component {
    static template = "CaptureImage";
    static components = {
        FileUploader,
    };
    static props = {
        ...standardFieldProps,
        enableZoom: { type: Boolean, optional: true },
        zoomDelay: { type: Number, optional: true },
        previewImage: { type: String, optional: true },
        acceptedFileExtensions: { type: String, optional: true },
        width: { type: Number, optional: true },
        height: { type: Number, optional: true },
        reload: { type: Boolean, optional: true },
    };
    static defaultProps = {
        acceptedFileExtensions: "image/*",
        reload: true,
    };
    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.isMobile = isMobileOS();
        this.state = useState({
            isValid: true,
            stream: null,
        });
        this.player = useRef("player");
        this.capture = useRef("capture");
        this.camera = useRef("camera");
        this.save_image = useRef("save_image");
        this.rawCacheKey = this.props.record.data.write_date;

        // Initialize props.value from record data if not set (for persistence after refresh)
        if (!this.props.value && this.props.record.data[this.props.name]) {
            this.props.value = this.props.record.data[this.props.name];
            this.state.isValid = true;
        }

        onWillUpdateProps((nextProps) => {
            const { record } = this.props;
            const { record: nextRecord } = nextProps;
            if (record.resId !== nextRecord.resId || nextRecord.mode === "readonly") {
                this.rawCacheKey = nextRecord.data.write_date;
            }
            // Sync props.value with record data when record updates
            if (nextRecord.data[nextProps.name] && nextRecord.data[nextProps.name] !== nextProps.value) {
                nextProps.value = nextRecord.data[nextProps.name];
            }
        });
    }

    get sizeStyle() {
        // For getting image style details
        let style = "";
        if (this.props.width) {
            style += `max-width: ${this.props.width}px;`;
        }
        if (this.props.height) {
            style += `max-height: ${this.props.height}px;`;
        }
        return style;
    }
    get hasTooltip() {
        return (
            this.props.enableZoom && this.props.readonly && this.props.record.data[this.props.name]
        );
    }
    getUrl(previewFieldName) {
        // getting the details and url of the image
        if (!this.props.reload && this.lastURL) {
            return this.lastURL;
        }
        if (this.state.isValid && this.props.record.data[this.props.name]) {
            if (isBinarySize(this.props.record.data[this.props.name])) {
                if (!this.rawCacheKey) {
                    this.rawCacheKey = this.props.record.data.write_date;
                }
                this.lastURL = url("/web/image", {
                    model: this.props.record.resModel,
                    id: this.props.record.resId,
                    field: previewFieldName,
                    unique: imageCacheKey(this.rawCacheKey),
                });
            } else {
                // Use magic-word technique for detecting image type
                const magic =
                    fileTypeMagicWordMap[this.props.record.data[this.props.name][0]] || "png";
                this.lastURL = `data:image/${magic};base64,${this.props.record.data[this.props.name]
                    }`;
            }
            return this.lastURL;
        }
        return placeholder;
    }
    onFileRemove() {
        // removing the images
        this.state.isValid = true;
        this.props.record.update({ [this.props.name]: false });
    }
    async onFileUploaded(info) {
        // Upload the images
        this.state.isValid = true;
        this.rawCacheKey = null;
        this.props.record.update({ [this.props.name]: info.data });
    }
    onFileCaptureImage() {
        // Open a window for open the image and capture it
        var field = this.props.name;
        var id = this.props.record.data.id;
        var model = this.props.record.resModel;
    }

    async checkCameraPermission() {
        try {
            // Check if permissions API is available
            if (navigator.permissions && navigator.permissions.query) {
                const permissionStatus = await navigator.permissions.query({ name: 'camera' });
                console.log("Camera permission state:", permissionStatus.state);
                if (permissionStatus.state === "granted") {
                    return { allowed: true, state: "granted" };
                } else if (permissionStatus.state === "prompt") {
                    return { allowed: true, state: "prompt" }; // Allow prompt to trigger browser dialog
                } else if (permissionStatus.state === "denied") {
                    return { allowed: false, state: "denied" };
                }
            }
            // If permissions API is not available, try to access camera anyway
            return { allowed: true, state: "unknown" };
        } catch (error) {
            console.error("Error checking camera permission:", error);
            // If permission check fails, still try to access camera
            return { allowed: true, state: "unknown" };
        }
    }

    async OnClickOpenCamera() {
        // opening the camera for capture the image
        try {
            const permissionCheck = await this.checkCameraPermission();
            if (permissionCheck.state === "denied") {
                this.notification.add(
                    _t("Camera access is denied. Please enable camera permissions in your browser settings and try again."),
                    { type: "warning", title: _t("Camera Permission Required") }
                );
                return;
            }

            // Try to access camera - this will trigger browser permission prompt if needed
            if (!this.player.el) {
                console.error("Video element not found");
                return;
            }

            // Hide image if shown, show video
            const previewImg = this.player.el.parentElement.querySelector('.o_preview_img');
            if (previewImg) {
                previewImg.style.display = 'none';
            }

            this.player.el.classList.remove('d-none');
            if (this.capture.el) {
                this.capture.el.classList.remove('d-none');
            }
            if (this.camera.el) {
                this.camera.el.classList.add('d-none');
            }

            // Use back camera (environment) on mobile devices
            // If environment camera is not available, fall back to default camera
            let videoConstraints = {
                facingMode: 'environment' // 'environment' = back camera, 'user' = front camera
            };

            try {
                this.state.stream = await navigator.mediaDevices.getUserMedia({
                    video: videoConstraints,
                    audio: false
                });
            } catch (envError) {
                // If back camera fails, try default camera
                console.log("Back camera not available, trying default camera:", envError);
                videoConstraints = true; // Use default camera
                this.state.stream = await navigator.mediaDevices.getUserMedia({
                    video: videoConstraints,
                    audio: false
                });
            }

            if (this.player.el) {
                this.player.el.srcObject = this.state.stream;
            }
        } catch (error) {
            console.error("Error accessing camera:", error);
            if (this.player.el) {
                this.player.el.classList.add('d-none');
            }
            if (this.capture.el) {
                this.capture.el.classList.add('d-none');
            }
            if (this.camera.el) {
                this.camera.el.classList.remove('d-none');
            }

            // Show image again if it was hidden
            const previewImg = document.querySelector('.o_preview_img');
            if (previewImg) {
                previewImg.style.display = '';
            }

            let errorMessage = _t("Error accessing camera");
            if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
                errorMessage = _t("Camera access denied. Please allow camera access in your browser settings and reload the page.");
            } else if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
                errorMessage = _t("No camera found. Please connect a camera device.");
            } else if (error.name === "NotReadableError" || error.name === "TrackStartError") {
                errorMessage = _t("Camera is being used by another application. Please close other apps using the camera and try again.");
            } else {
                errorMessage = _t("Error accessing camera: %s").replace("%s", error.message);
            }

            this.notification.add(errorMessage, {
                type: "danger",
                title: _t("Camera Error")
            });
        }
    }
    stopTracksOnMediaStream(mediaStream) {
        for (const track of mediaStream.getTracks()) {
            track.stop();
        }
    }
    async OnClickCaptureImage() {
        // Capture the image from webcam
        if (!this.player.el) {
            console.error("Video element not found");
            return;
        }

        var canvas = document.getElementById('snapshot');
        if (!canvas) {
            console.error("Canvas element not found");
            return;
        }

        var context = canvas.getContext('2d');
        var image = document.getElementById('image');

        // Use actual video dimensions for better quality
        var videoWidth = this.player.el.videoWidth || 1920;
        var videoHeight = this.player.el.videoHeight || 1080;
        canvas.width = videoWidth;
        canvas.height = videoHeight;

        // Draw video frame to canvas
        context.drawImage(this.player.el, 0, 0, videoWidth, videoHeight);

        // Convert to base64 data URL
        this.url = canvas.toDataURL('image/png');

        // Extract base64 data (remove data:image/png;base64, prefix)
        const base64Data = this.url.split(',')[1];

        // Update hidden input
        if (image) {
            image.value = this.url;
        }

        // Stop video stream and hide video
        if (this.state.stream) {
            this.stopTracksOnMediaStream(this.state.stream);
            this.state.stream = null;
        }
        if (this.player.el) {
            this.player.el.srcObject = null;
            this.player.el.classList.add('d-none');
        }

        // Show canvas as preview immediately after capture
        canvas.classList.remove('d-none');
        canvas.style.width = '100%';
        canvas.style.height = 'auto';
        canvas.style.display = 'block';
        canvas.style.borderRadius = '12px';

        // Hide any existing saved image preview to show captured canvas
        const existingImg = this.player.el.parentElement.querySelector('.o_preview_img');
        if (existingImg) {
            existingImg.style.display = 'none';
        }

        // Don't update props.value yet - keep canvas visible as preview
        // Canvas will show the captured image immediately
        // props.value will be updated when user clicks Save Image

        // Show save button, hide capture button
        if (this.save_image.el) {
            this.save_image.el.classList.remove('d-none');
        }
        if (this.capture.el) {
            this.capture.el.classList.add('d-none');
        }
    }
    async OnClickSaveImage() {
        // Saving the image to that field
        var self = this;
        await rpc('/web/dataset/call_kw', {
            model: 'image.capture',
            method: 'action_save_image',
            args: [[], this.url],
            kwargs: {}
        }).then(async function (results) {
            // Stop video stream first
            if (self.state.stream) {
                self.stopTracksOnMediaStream(self.state.stream);
                self.state.stream = null;
            }

            if (self.player.el) {
                self.player.el.classList.add('d-none');
                self.player.el.srcObject = null;
            }

            // Update props and state before updating UI
            self.props.value = results;
            self.state.isValid = true;

            // Reset cache to force image reload
            self.rawCacheKey = null;
            self.lastURL = null;

            var data = {
                data: results,
                name: "ImageFile.png",
                objectUrl: null,
                size: 106252,
                type: "image/png"
            };

            // Update the record to trigger re-render with new image
            self.onFileUploaded(data);

            // Save the record to database so it persists after refresh
            // Only save if record has an ID (already exists in database)
            if (self.props.record.resId) {
                try {
                    console.log("Saving image to database:", {
                        model: self.props.record.resModel,
                        resId: self.props.record.resId,
                        field: self.props.name,
                        imageLength: results ? results.length : 0
                    });

                    // Use RPC to directly write to the database
                    const writeResult = await rpc('/web/dataset/call_kw', {
                        model: self.props.record.resModel,
                        method: 'write',
                        args: [[self.props.record.resId], { [self.props.name]: results }],
                        kwargs: {}
                    });

                    console.log("Write result:", writeResult);

                    if (writeResult !== false) {
                        // Verify the data was saved by reading it back
                        const readResult = await rpc('/web/dataset/call_kw', {
                            model: self.props.record.resModel,
                            method: 'read',
                            args: [[self.props.record.resId], [self.props.name]],
                            kwargs: {}
                        });

                        console.log("Read back from database:", readResult);

                        if (readResult && readResult[0] && readResult[0][self.props.name]) {
                            // Update record data with saved value from database
                            const savedImageData = readResult[0][self.props.name];
                            self.props.record.data[self.props.name] = savedImageData;

                            // Also update props.value to ensure it matches database
                            self.props.value = savedImageData;

                            // Update state to ensure image is valid
                            self.state.isValid = true;

                            // Update rawCacheKey to force image refresh
                            self.rawCacheKey = new Date().getTime();
                            self.lastURL = null;

                            // Force component to re-render by updating the record
                            self.props.record.update({ [self.props.name]: savedImageData });

                            // Hide canvas and show saved image
                            var snapshot = document.getElementById('snapshot');
                            if (snapshot) {
                                snapshot.classList.add('d-none');
                                snapshot.style.display = 'none';
                            }

                            // Ensure saved image preview is visible
                            setTimeout(function () {
                                const previewImg = document.querySelector('.o_preview_img');
                                if (previewImg) {
                                    previewImg.style.display = '';
                                }
                            }, 50);

                            self.notification.add(
                                _t("Image saved successfully to database"),
                                { type: "success", title: _t("Success") }
                            );
                        } else {
                            throw new Error("Image not found after save");
                        }
                    } else {
                        throw new Error("Write operation returned false");
                    }
                } catch (error) {
                    console.error("Error saving record:", error);
                    self.notification.add(
                        _t("Error saving record: %s. Please save the form manually.", error.message || error),
                        { type: "warning", title: _t("Save Warning") }
                    );
                }
            } else {
                // If record doesn't have ID yet, notify user to save the form
                console.log("Record has no ID, cannot save to database");
                self.notification.add(
                    _t("Please save the form first, then capture the image to persist it."),
                    { type: "info", title: _t("Save Required") }
                );
            }

            // Hide buttons immediately
            if (self.capture.el) {
                self.capture.el.classList.add('d-none');
            }
            if (self.save_image.el) {
                self.save_image.el.classList.add('d-none');
            }
            if (self.camera.el) {
                self.camera.el.classList.remove('d-none');
            }
        }).catch(function (error) {
            console.error("Error saving image:", error);
            self.notification.add(
                _t("Error saving image. Please try again."),
                { type: "danger", title: _t("Save Error") }
            );
        });
    }
    onLoadFailed() {
        this.state.isValid = false;
        this.notification.add(this.env._t("Could not display the selected image"), {
            type: "danger",
        });
    }
}
export const ImageCapture = {
    component: imageCapture,
    displayName: _t("Image"),
    supportedOptions: [
        {
            label: _t("Reload"),
            name: "reload",
            type: "boolean",
            default: true,
        },
        {
            label: _t("Enable zoom"),
            name: "zoom",
            type: "boolean",
        },
        {
            label: _t("Zoom delay"),
            name: "zoom_delay",
            type: "number",
            help: _t("Delay the apparition of the zoomed image with a value in milliseconds"),
        },
        {
            label: _t("Accepted file extensions"),
            name: "accepted_file_extensions",
            type: "string",
        },
        {
            label: _t("Size"),
            name: "size",
            type: "selection",
            choices: [
                { label: _t("Small"), value: "[0,90]" },
                { label: _t("Medium"), value: "[0,180]" },
                { label: _t("Large"), value: "[0,270]" },
            ],
        },
        {
            label: _t("Preview image"),
            name: "preview_image",
            type: "field",
            availableTypes: ["binary"],
        },
    ],
    supportedTypes: ["binary"],
    fieldDependencies: [{ name: "write_date", type: "datetime" }],
    isEmpty: () => false,
    extractProps: ({ attrs, options }) => ({
        enableZoom: options.zoom,
        zoomDelay: options.zoom_delay,
        previewImage: options.preview_image,
        acceptedFileExtensions: options.accepted_file_extensions,
        width: options.size && Boolean(options.size[0]) ? options.size[0] : attrs.width,
        height: options.size && Boolean(options.size[1]) ? options.size[1] : attrs.height,
        reload: "reload" in options ? Boolean(options.reload) : true,
    }),
};
registry.category("fields").add("capture_image", ImageCapture);
