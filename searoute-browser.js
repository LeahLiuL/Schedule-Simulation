/**
 * Browser-side searoute implementation
 * Calculates actual sailing distance using marnet maritime network data
 * No external dependencies — pure JavaScript
 * 
 * Uses: Dijkstra pathfinding on global maritime network
 * Data source: Eurostat marnet_densified.json (618KB)
 * 
 * The marnet data is loaded lazily from CDN on first use and cached.
 */

// ========== MATH UTILITIES (replacing @turf) ==========

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;
const EARTH_RADIUS_KM = 6371.0088;
const EARTH_RADIUS_NM = 3440.065; // nautical miles
const NM_PER_MILE = 1.15078;

function toRad(deg) { return deg * DEG2RAD; }
function toDeg(rad) { return rad * RAD2DEG; }

// Haversine distance in kilometers
function haversineKm(lat1, lon1, lat2, lon2) {
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return EARTH_RADIUS_KM * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Rhumb (loxodrome) distance in nautical miles
function rhumbDistanceNM(lat1, lon1, lat2, lon2) {
    const dLat = toRad(lat2 - lat1);
    let dLon = toRad(lon2 - lon1);
    // Handle wrapping
    if (Math.abs(dLon) > Math.PI) {
        dLon = dLon > 0 ? -(2 * Math.PI - dLon) : (2 * Math.PI + dLon);
    }
    const dPhi = Math.log(Math.tan(Math.PI / 4 + toRad(lat2) / 2) / Math.tan(Math.PI / 4 + toRad(lat1) / 2));
    const q = Math.abs(dLat) > 1e-12 ? dLat / dPhi : Math.cos(toRad(lat1));
    const d = Math.sqrt(dLat * dLat + q * q * dLon * dLon);
    return EARTH_RADIUS_NM * d;
}

// Point-to-segment distance in kilometers (for snapping to network)
function pointToSegmentDistKm(px, py, ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay;
    if (dx === 0 && dy === 0) return haversineKm(px, py, ax, ay);
    const len2 = dx * dx + dy * dy;
    let t = ((px - ax) * dx + (py - ay) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const cx = ax + t * dx, cy = ay + t * dy;
    return haversineKm(px, py, cx, cy);
}

// GeoJSON line length in nautical miles
function lineLengthNM(coords) {
    let total = 0;
    for (let i = 1; i < coords.length; i++) {
        total += haversineKm(coords[i - 1][1], coords[i - 1][0], coords[i][1], coords[i][0]);
    }
    return total / 1.852; // km to nautical miles
}

// ========== BINARY MIN HEAP (for Dijkstra) ==========

class MinHeap {
    constructor() { this.data = []; }

    get size() { return this.data.length; }

    push(item) {
        this.data.push(item);
        this._bubbleUp(this.data.length - 1);
    }

    pop() {
        const top = this.data[0];
        const last = this.data.pop();
        if (this.data.length > 0) {
            this.data[0] = last;
            this._sinkDown(0);
        }
        return top;
    }

    _bubbleUp(i) {
        while (i > 0) {
            const parent = (i - 1) >> 1;
            if (this.data[i].dist < this.data[parent].dist) {
                [this.data[i], this.data[parent]] = [this.data[parent], this.data[i]];
                i = parent;
            } else break;
        }
    }

    _sinkDown(i) {
        const n = this.data.length;
        while (true) {
            let smallest = i;
            const left = 2 * i + 1, right = 2 * i + 2;
            if (left < n && this.data[left].dist < this.data[smallest].dist) smallest = left;
            if (right < n && this.data[right].dist < this.data[smallest].dist) smallest = right;
            if (smallest === i) break;
            [this.data[i], this.data[smallest]] = [this.data[smallest], this.data[i]];
            i = smallest;
        }
    }
}

// ========== MARNET NETWORK & DIJKSTRA ==========

let marnetData = null;   // GeoJSON FeatureCollection
let routeFinder = null;  // Dijkstra pathfinder instance
let marnetLoadPromise = null;

// Load marnet data from CDN (cached after first load)
function loadMarnet() {
    if (marnetData) return Promise.resolve(marnetData);
    if (marnetLoadPromise) return marnetLoadPromise;

    marnetLoadPromise = fetch('https://unpkg.com/searoute-js@0.1.0/data/marnet_densified.json')
        .then(r => r.json())
        .then(data => {
            marnetData = data;
            routeFinder = new GeoJSONPathFinder(data);
            return marnetData;
        })
        .catch(err => {
            marnetLoadPromise = null;
            throw err;
        });
    return marnetLoadPromise;
}

// Minimal Dijkstra pathfinder on GeoJSON network
// Based on geojson-path-finder logic
class GeoJSONPathFinder {
    constructor(geojson) {
        this.graph = new Map();  // coordKey -> [{node, weight}]
        this.features = geojson.features;
        this.allCoords = [];     // Pre-extracted all unique coords for snap lookup
        this.coordSet = new Set();

        // Build adjacency graph from LineString features
        for (const feature of geojson.features) {
            if (feature.geometry.type !== 'LineString') continue;
            const coords = feature.geometry.coordinates;
            for (let i = 0; i < coords.length; i++) {
                const key = this.coordKey(coords[i]);
                if (!this.coordSet.has(key)) {
                    this.coordSet.add(key);
                    this.allCoords.push(coords[i]); // [lon, lat]
                }
            }
        }

        // Build edges
        for (const feature of geojson.features) {
            if (feature.geometry.type !== 'LineString') continue;
            const coords = feature.geometry.coordinates;
            for (let i = 0; i < coords.length - 1; i++) {
                const k1 = this.coordKey(coords[i]);
                const k2 = this.coordKey(coords[i + 1]);
                const dist = haversineKm(coords[i][1], coords[i][0], coords[i + 1][1], coords[i + 1][0]);
                this.addEdge(k1, k2, dist);
                this.addEdge(k2, k1, dist);
            }
        }
    }

    coordKey(coord) {
        // Round to 5 decimal places (~1m precision) for dedup
        return Math.round(coord[0] * 100000) + ',' + Math.round(coord[1] * 100000);
    }

    addEdge(from, to, weight) {
        if (!this.graph.has(from)) this.graph.set(from, []);
        this.graph.get(from).push({ node: to, weight });
    }

    // Find shortest path between two [lon, lat] coordinates
    findPath(startCoord, endCoord) {
        // Snap to nearest network vertices
        const startKey = this.snapToVertex(startCoord);
        const endKey = this.snapToVertex(endCoord);

        if (!startKey || !endKey) return null;

        // Dijkstra with binary heap
        const dist = new Map();
        const prev = new Map();
        const visited = new Set();

        dist.set(startKey, 0);
        const heap = new MinHeap();
        heap.push({ node: startKey, dist: 0 });

        while (heap.size > 0) {
            const { node: current } = heap.pop();

            if (visited.has(current)) continue;
            visited.add(current);

            if (current === endKey) break;

            const edges = this.graph.get(current);
            if (!edges) continue;

            for (const edge of edges) {
                if (visited.has(edge.node)) continue;
                const newDist = dist.get(current) + edge.weight;
                if (!dist.has(edge.node) || newDist < dist.get(edge.node)) {
                    dist.set(edge.node, newDist);
                    prev.set(edge.node, current);
                    heap.push({ node: edge.node, dist: newDist });
                }
            }
        }

        if (!prev.has(endKey)) return null;

        // Reconstruct path
        const path = [];
        let current = endKey;
        while (current !== undefined) {
            const [lon, lat] = current.split(',').map(Number);
            path.unshift([lon / 100000, lat / 100000]);
            current = prev.get(current);
        }

        return { path, distance: dist.get(endKey) };
    }

    // Find nearest network vertex to a given [lon, lat] coordinate
    snapToVertex(coord) {
        let bestKey = null;
        let bestDist = Infinity;

        // Use equirectangular approximation for fast pre-filtering
        // Only compute precise haversine for nearby candidates
        const lon1 = coord[0], lat1 = coord[1];
        const x1 = Math.cos(toRad(lat1)) * toRad(lon1);
        const y1 = toRad(lat1);
        const cosLat = Math.cos(toRad(lat1));
        const R = EARTH_RADIUS_KM;

        for (const c of this.allCoords) {
            // Equirectangular fast distance (km)
            const x2 = cosLat * toRad(c[0]);
            const y2 = toRad(c[1]);
            const dx = x2 - x1;
            const dy = y2 - y1;
            const fastDist = R * Math.sqrt(dx * dx + dy * dy);

            if (fastDist < bestDist) {
                // Refine with haversine for accurate comparison
                const preciseDist = haversineKm(lat1, lon1, c[1], c[0]);
                if (preciseDist < bestDist) {
                    bestDist = preciseDist;
                    bestKey = this.coordKey(c);
                }
            }
        }

        return bestKey;
    }
}

// ========== MAIN SEAROUTE FUNCTION ==========

/**
 * Calculate shortest maritime route between two points.
 * @param {number} lon1 - Origin longitude
 * @param {number} lat1 - Origin latitude  
 * @param {number} lon2 - Destination longitude
 * @param {number} lat2 - Destination latitude
 * @returns {Promise<{distance_nm: number, path: number[][]}|null>}
 */
async function calcSearoute(lon1, lat1, lon2, lat2) {
    const data = await loadMarnet();

    if (!routeFinder) return null;

    const result = routeFinder.findPath([lon1, lat1], [lon2, lat2]);

    if (!result) return null;

    const distanceNm = lineLengthNM(result.path);

    return {
        distance_nm: Math.round(distanceNm),
        path: result.path
    };
}
