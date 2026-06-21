/** @odoo-module **/
/* version: v10-google-maps-real-key */

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, onWillUnmount, useRef, useState, useEffect } from "@odoo/owl";

const GOOGLE_MAPS_API_KEY = "AIzaSyCQ1XvoKRmX1qqo2XwlLj2C2gCIiCjtgFE";
const JSZIP_CDN = "https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js";

// Load JSZip script once
function loadScript(url) {
    if (document.querySelector(`script[src="${url}"]`)) return Promise.resolve();
    return new Promise((res, rej) => {
        const s = document.createElement("script");
        s.src = url; s.async = true;
        s.onload = res;
        s.onerror = () => rej(new Error("Failed to load: " + url));
        document.head.appendChild(s);
    });
}

// Load Google Maps API with callback — safe against double-load
function loadGoogleMaps() {
    return new Promise((resolve, reject) => {
        if (window.google && window.google.maps && window.google.maps.Map) {
            return resolve();
        }
        if (window.__gmLoading) {
            return window.__gmLoading.then(resolve).catch(reject);
        }
        const cb = "__gmReady_" + Date.now();
        window.__gmLoading = new Promise((res, rej) => {
            window[cb] = () => {
                delete window[cb];
                delete window.__gmLoading;
                res();
                resolve();
            };
            const s = document.createElement("script");
            s.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&callback=${cb}&v=weekly`;
            s.async = true;
            s.defer = true;
            s.onerror = () => {
                const e = new Error("Google Maps API failed to load.");
                delete window[cb];
                delete window.__gmLoading;
                rej(e); reject(e);
            };
            document.head.appendChild(s);
        });
    });
}

export class KmlViewer extends Component {
    static template = "bhukhadan_core.KmlViewer";
    static props = { ...standardFieldProps };

    setup() {
        this.mapContainer = useRef("mapContainer");
        this.map = null;
        this.markers = [];
        this.polylines = [];
        this.polygons = [];

        this.state = useState({
            isLoading: true,
            error: null,
            status: "Initializing...",
            featureCount: 0,
        });

        onMounted(async () => {
            try {
                this.state.status = "Loading JSZip...";
                await loadScript(JSZIP_CDN);

                this.state.status = "Loading Google Maps...";
                await loadGoogleMaps();

                this.state.status = "Initializing map...";
                await new Promise(r => setTimeout(r, 80));

                this.initMap();
                await this.renderKml();
                this.state.isLoading = false;
            } catch (e) {
                console.error("KML Viewer V10:", e);
                this.state.error = e.message;
                this.state.isLoading = false;
            }
        });

        onWillUnmount(() => {
            this.clearOverlays();
            this.map = null;
        });

        useEffect(() => {
            if (!this.state.isLoading && this.map) {
                this.renderKml();
            }
        }, () => [this.props.record.data[this.props.name]]);
    }

    // ─── Map initialisation ───────────────────────────────────────────────
    initMap() {
        const el = this.mapContainer.el;
        if (!el || this.map) return;

        // ── Force the container to full width BEFORE Google Maps reads its size ──
        el.style.width = "100%";
        el.style.height = "600px";
        el.style.display = "block";
        // Walk up to Odoo field wrapper and remove any width constraints
        let node = el.parentElement;
        for (let i = 0; i < 6 && node; i++) {
            node.style.width = "100%";
            node.style.maxWidth = "none";
            node = node.parentElement;
        }

        this.map = new google.maps.Map(el, {
            center: { lat: 22.5937, lng: 80.9629 },
            zoom: 5,
            mapTypeId: google.maps.MapTypeId.HYBRID,
            mapTypeControl: true,
            mapTypeControlOptions: {
                style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
                position: google.maps.ControlPosition.TOP_RIGHT,
                mapTypeIds: [
                    google.maps.MapTypeId.ROADMAP,
                    google.maps.MapTypeId.SATELLITE,
                    google.maps.MapTypeId.HYBRID,
                    google.maps.MapTypeId.TERRAIN,
                ],
            },
            fullscreenControl: true,
            streetViewControl: false,
            zoomControl: true,
            gestureHandling: "greedy",
        });

        // Trigger resize multiple times to catch late layout shifts
        [100, 300, 600, 1000].forEach(ms =>
            setTimeout(() => { if (this.map) google.maps.event.trigger(this.map, "resize"); }, ms)
        );

        // ── My Location button ────────────────────────────────────────────
        this.addMyLocationButton();

        console.log("KML Viewer V10: Google Map initialized (HYBRID mode)");
    }

    addMyLocationButton() {
        const btn = document.createElement("button");
        btn.title = "My Location";
        btn.style.cssText = `
            background:#fff;
            border:none;
            border-radius:3px;
            box-shadow:0 1px 4px rgba(0,0,0,0.3);
            cursor:pointer;
            margin:10px;
            padding:8px;
            width:40px;
            height:40px;
            display:flex;
            align-items:center;
            justify-content:center;
        `;
        btn.innerHTML = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20">
                <path fill="#1a73e8" d="M12 8c-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4-1.79-4-4-4zm8.94 3c-.46-4.17-3.77-7.48-7.94-7.94V1h-2v2.06C6.83 3.52 3.52 6.83 3.06 11H1v2h2.06c.46 4.17 3.77 7.48 7.94 7.94V23h2v-2.06c4.17-.46 7.48-3.77 7.94-7.94H23v-2h-2.06zM12 19c-3.87 0-7-3.13-7-7s3.13-7 7-7 7 3.13 7 7-3.13 7-7 7z"/>
            </svg>`;

        btn.addEventListener("click", () => this.goToMyLocation());

        // Add button to map (RIGHT_BOTTOM position)
        this.map.controls[google.maps.ControlPosition.RIGHT_BOTTOM].push(btn);
    }

    goToMyLocation() {
        if (!navigator.geolocation) {
            this.state.status = "⚠ Geolocation not supported by this browser.";
            return;
        }
        this.state.status = "Detecting your location...";
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const latlng = new google.maps.LatLng(pos.coords.latitude, pos.coords.longitude);
                this.map.panTo(latlng);
                this.map.setZoom(14);

                // Remove old location marker if exists
                if (this._locationMarker) this._locationMarker.setMap(null);

                this._locationMarker = new google.maps.Marker({
                    position: latlng,
                    map: this.map,
                    title: "My Location",
                    icon: {
                        path: google.maps.SymbolPath.CIRCLE,
                        scale: 10,
                        fillColor: "#1a73e8",
                        fillOpacity: 1,
                        strokeColor: "#fff",
                        strokeWeight: 3,
                    },
                    zIndex: 9999,
                });

                const iw = new google.maps.InfoWindow({ content: "<b>📍 Your Location</b>" });
                iw.open(this.map, this._locationMarker);
                this.state.status = `📍 Location found (${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)})`;
            },
            (err) => {
                this.state.status = `⚠ Location error: ${err.message}`;
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }

    // ─── Helpers ──────────────────────────────────────────────────────────
    clearOverlays() {
        (this.markers || []).forEach(m => m.setMap(null));
        (this.polylines || []).forEach(p => p.setMap(null));
        (this.polygons || []).forEach(p => p.setMap(null));
        this.markers = [];
        this.polylines = [];
        this.polygons = [];
    }

    /**
     * In Odoo 18, saved binary fields return `true` (not base64).
     * Fetch the actual bytes via /web/content for saved records.
     */
    async fetchBinaryBytes() {
        const value = this.props.record.data[this.props.name];
        if (!value) return null;

        // Unsaved / freshly-uploaded — value is a base64 string
        if (typeof value === "string" && value.length > 10) {
            return this.base64ToBytes(value);
        }

        // Saved record — fetch from server
        const model = this.props.record.resModel;
        const id = this.props.record.resId;
        const field = this.props.name;

        if (!id) throw new Error("Please save the record first to view the map.");

        this.state.status = "Downloading KML/KMZ...";
        const url = `/web/content?model=${encodeURIComponent(model)}&id=${id}&field=${encodeURIComponent(field)}&download=1`;
        const resp = await fetch(url, { credentials: "same-origin" });
        if (!resp.ok) throw new Error(`Download failed (HTTP ${resp.status})`);
        return new Uint8Array(await resp.arrayBuffer());
    }

    base64ToBytes(b64) {
        let s = b64.replace(/[\s\r\n]+/g, "").replace(/-/g, "+").replace(/_/g, "/");
        const m = s.length % 4;
        if (m === 2) s += "=="; else if (m === 3) s += "=";
        const bin = atob(s);
        const out = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
        return out;
    }

    parseCoords(str) {
        return str.trim().split(/\s+/).map(t => {
            const p = t.split(",");
            const lng = parseFloat(p[0]), lat = parseFloat(p[1]);
            return (!isNaN(lat) && !isNaN(lng)) ? new google.maps.LatLng(lat, lng) : null;
        }).filter(Boolean);
    }

    kmlColorToHex(kml) {
        if (!kml || kml.length < 6) return "#2979ff";
        const c = kml.replace(/[^0-9a-fA-F]/g, "").padStart(8, "0");
        return `#${c.slice(6, 8)}${c.slice(4, 6)}${c.slice(2, 4)}`;
    }

    getStyle(pm) {
        const st = pm.querySelector("Style");
        return {
            strokeColor: st ? this.kmlColorToHex(st.querySelector("LineStyle > color")?.textContent) : "#2979ff",
            fillColor: st ? this.kmlColorToHex(st.querySelector("PolyStyle > color")?.textContent) : "#2979ff",
            strokeOpacity: 1,
            fillOpacity: 0.35,
            strokeWeight: 2,
        };
    }

    // ─── KML parsing ──────────────────────────────────────────────────────
    parsePlacemarks(dom, bounds) {
        let count = 0;

        dom.querySelectorAll("Placemark").forEach(pm => {
            const name = pm.querySelector("name")?.textContent?.trim() || "";
            const desc = pm.querySelector("description")?.textContent?.trim() || "";
            const html = (name || desc)
                ? `<div style="font-family:sans-serif;max-width:280px"><b>${name}</b>${desc ? "<br><small>" + desc + "</small>" : ""}</div>`
                : null;

            // Points
            pm.querySelectorAll("Point > coordinates").forEach(c => {
                const pts = this.parseCoords(c.textContent);
                if (!pts.length) return;
                const mk = new google.maps.Marker({ position: pts[0], map: this.map, title: name });
                if (html) {
                    const iw = new google.maps.InfoWindow({ content: html });
                    mk.addListener("click", () => iw.open(this.map, mk));
                }
                this.markers.push(mk);
                bounds.extend(pts[0]);
                count++;
            });

            // LineStrings (direct + in MultiGeometry)
            pm.querySelectorAll("LineString > coordinates, MultiGeometry LineString > coordinates").forEach(c => {
                const pts = this.parseCoords(c.textContent);
                if (pts.length < 2) return;
                const sty = this.getStyle(pm);
                const pl = new google.maps.Polyline({
                    path: pts, map: this.map,
                    strokeColor: sty.strokeColor, strokeOpacity: 1, strokeWeight: 3,
                });
                if (html) {
                    const iw = new google.maps.InfoWindow({ content: html });
                    pl.addListener("click", e => { iw.setPosition(e.latLng); iw.open(this.map); });
                }
                this.polylines.push(pl);
                pts.forEach(p => bounds.extend(p));
                count++;
            });

            // Polygons
            pm.querySelectorAll("Polygon").forEach(poly => {
                const oc = poly.querySelector("outerBoundaryIs > LinearRing > coordinates");
                if (!oc) return;
                const pts = this.parseCoords(oc.textContent);
                if (pts.length < 3) return;
                const sty = this.getStyle(pm);
                const pg = new google.maps.Polygon({
                    paths: pts, map: this.map,
                    strokeColor: sty.strokeColor, strokeOpacity: 1, strokeWeight: 2,
                    fillColor: sty.fillColor, fillOpacity: sty.fillOpacity,
                });
                if (html) {
                    const iw = new google.maps.InfoWindow({ content: html });
                    pg.addListener("click", e => { iw.setPosition(e.latLng); iw.open(this.map); });
                }
                this.polygons.push(pg);
                pts.forEach(p => bounds.extend(p));
                count++;
            });
        });

        return count;
    }

    // ─── Main render ──────────────────────────────────────────────────────
    async renderKml() {
        if (!this.map) return;
        this.clearOverlays();

        try {
            const bytes = await this.fetchBinaryBytes();
            if (!bytes) {
                this.state.status = "No KML/KMZ file uploaded.";
                return;
            }
            this.state.error = null;

            let kmlString = "";

            // KMZ = ZIP (magic: PK = 0x50 0x4B)
            if (bytes[0] === 0x50 && bytes[1] === 0x4B) {
                this.state.status = "Extracting KMZ...";
                if (!window.JSZip) throw new Error("JSZip not loaded.");
                const zip = await new JSZip().loadAsync(bytes);
                const entries = Object.keys(zip.files).filter(n => n.toLowerCase().endsWith(".kml"));
                const entry = entries.find(n => n.toLowerCase() === "doc.kml") || entries[0];
                if (!entry) throw new Error("No .kml file inside KMZ.");
                kmlString = await zip.file(entry).async("string");
            } else {
                kmlString = new TextDecoder("utf-8").decode(bytes);
            }

            if (!kmlString.trim()) throw new Error("File is empty.");

            this.state.status = "Parsing KML...";
            const dom = new DOMParser().parseFromString(kmlString, "text/xml");
            const err = dom.querySelector("parsererror");
            if (err) throw new Error("XML error: " + err.textContent.slice(0, 100));

            this.state.status = "Rendering on map...";
            const bounds = new google.maps.LatLngBounds();
            const count = this.parsePlacemarks(dom, bounds);

            if (count === 0) {
                this.state.status = "⚠ No geometry found in KML.";
                return;
            }

            if (!bounds.isEmpty()) {
                this.map.fitBounds(bounds, { top: 40, right: 40, bottom: 40, left: 40 });
                google.maps.event.addListenerOnce(this.map, "idle", () => {
                    if (this.map.getZoom() > 18) this.map.setZoom(16);
                });
            }

            // Final resize to guarantee full-width rendering
            setTimeout(() => {
                if (this.map) google.maps.event.trigger(this.map, "resize");
            }, 250);

            this.state.featureCount = count;
            this.state.status = `✓ ${count} feature(s) loaded`;
            console.log("KML Viewer V10: rendered", count, "features");

        } catch (e) {
            console.error("KML Viewer V10:", e);
            this.state.error = "❌ " + e.message;
            this.state.status = "Failed.";
        }
    }
}

export const kmlViewer = {
    component: KmlViewer,
    displayName: "KML Viewer (Google Maps)",
    supportedTypes: ["binary"],
};

registry.category("fields").add("kml_viewer", kmlViewer);
