// Route data structure matching the CSV format
export type AvailabilityState = "available" | "waiting" | "not-available" | "unknown";

export interface RouteSegment {
  routeId: string;
  category: string;
  segment: number;
  trainNumber: string;
  trainName: string;
  from: string;             // station code
  to: string;               // station code
  departure: string;
  arrival: string;
  distance: number;
  duration: number;
  waitBefore: number;
  liveSeatAvailability: string;
  liveFare: number;
  seatAvailable: boolean;
  // for booking/availability requests the frontend may occasionally
  // carry numeric stop ids obtained from backend. they are optional
  // because most of the route search responses only contain codes.
  from_stop_id?: number;
  to_stop_id?: number;
}

export interface Route {
  id: string;
  category: string;
  segments: RouteSegment[];
  totalTime: number;
  totalCost: number;
  totalTransfers: number;
  totalDistance: number;
  liveFareTotal: number;
  seatProbability: number;
  safetyScore: number;
}

export const categoryIcons: Record<string, string> = {
  "FASTEST": "⚡",
  "MOST DIRECT": "🚂",
  "BEST SEATS": "💺",
  "FAST": "⚡",
  "CHEAP": "💰",
  "BALANCED": "⚖️",
  "ALTERNATIVE": "🔄",
};

export const categoryColors: Record<string, string> = {
  "FASTEST": "bg-amber-500",
  "MOST DIRECT": "bg-blue-500",
  "BEST SEATS": "bg-green-500",
  "FAST": "bg-orange-500",
  "CHEAP": "bg-emerald-500",
  "BALANCED": "bg-purple-500",
  "ALTERNATIVE": "bg-slate-500",
};

// Sample data from PGT to KOTA
export const sampleRoutes: Route[] = [
  {
    id: "ROUTE_01",
    category: "FASTEST ⚡",
    segments: [
      {
        routeId: "ROUTE_01",
        category: "FASTEST ⚡",
        segment: 1,
        trainNumber: "22476",
        trainName: "CBE BKN AC S",
        from: "PGT",
        to: "BRC",
        departure: "16:20",
        arrival: "19:31",
        distance: 1598,
        duration: 1598,
        waitBefore: 0,
        liveSeatAvailability: "AVAILABLE-0120",
        liveFare: 826,
        seatAvailable: false,
      },
      {
        routeId: "ROUTE_01",
        category: "FASTEST ⚡",
        segment: 2,
        trainNumber: "12907",
        trainName: "BDTS SMPRK K",
        from: "BRC",
        to: "KOTA",
        departure: "23:12",
        arrival: "06:20",
        distance: 527,
        duration: 575,
        waitBefore: 221,
        liveSeatAvailability: "AVAILABLE-0045",
        liveFare: 1299,
        seatAvailable: false,
      },
    ],
    totalTime: 2394,
    totalCost: 2125,
    totalTransfers: 1,
    totalDistance: 2125,
    liveFareTotal: 2125,
    seatProbability: 0,
    safetyScore: 100,
  },
  {
    id: "ROUTE_02",
    category: "MOST DIRECT 🚂",
    segments: [
      {
        routeId: "ROUTE_02",
        category: "MOST DIRECT 🚂",
        segment: 1,
        trainNumber: "22476",
        trainName: "CBE BKN AC S",
        from: "PGT",
        to: "BRC",
        departure: "16:20",
        arrival: "19:31",
        distance: 1598,
        duration: 1598,
        waitBefore: 0,
        liveSeatAvailability: "AVAILABLE-030",
        liveFare: 830,
        seatAvailable: false,
      },
      {
        routeId: "ROUTE_02",
        category: "MOST DIRECT 🚂",
        segment: 2,
        trainNumber: "12431",
        trainName: "TVC-NZM RAJD",
        from: "BRC",
        to: "KOTA",
        departure: "00:24",
        arrival: "06:45",
        distance: 528,
        duration: 576,
        waitBefore: 293,
        liveSeatAvailability: "WL/20",
        liveFare: 1296,
        seatAvailable: true,
      },
    ],
    totalTime: 2467,
    totalCost: 2126,
    totalTransfers: 1,
    totalDistance: 2126,
    liveFareTotal: 2126,
    seatProbability: 50,
    safetyScore: 100,
  },
  {
    id: "ROUTE_03",
    category: "BEST SEATS 💺",
    segments: [
      {
        routeId: "ROUTE_03",
        category: "BEST SEATS 💺",
        segment: 1,
        trainNumber: "16791",
        trainName: "PUU-PGT PALA",
        from: "PGT",
        to: "KKZ",
        departure: "13:20",
        arrival: "03:41",
        distance: 328,
        duration: 394,
        waitBefore: 0,
        liveSeatAvailability: "AVAILABLE-020",
        liveFare: 650,
        seatAvailable: true,
      },
      {
        routeId: "ROUTE_03",
        category: "BEST SEATS 💺",
        segment: 2,
        trainNumber: "12483",
        trainName: "KCVL EXPRESS",
        from: "QLN",
        to: "KOTA",
        departure: "10:25",
        arrival: "02:55",
        distance: 2329,
        duration: 2409,
        waitBefore: 350,
        liveSeatAvailability: "AVAILABLE-015",
        liveFare: 2032,
        seatAvailable: true,
      },
    ],
    totalTime: 3192,
    totalCost: 2682,
    totalTransfers: 5,
    totalDistance: 2657,
    liveFareTotal: 2682,
    seatProbability: 83.33,
    safetyScore: 80,
  },
  {
    id: "ROUTE_04",
    category: "CHEAP 💰",
    segments: [
      {
        routeId: "ROUTE_04",
        category: "CHEAP 💰",
        segment: 1,
        trainNumber: "22476",
        trainName: "CBE BKN AC S",
        from: "PGT",
        to: "BRC",
        departure: "16:20",
        arrival: "19:31",
        distance: 1598,
        duration: 1598,
        waitBefore: 0,
        liveSeatAvailability: "AVAILABLE-010",
        liveFare: 820,
        seatAvailable: false,
      },
      {
        routeId: "ROUTE_04",
        category: "CHEAP 💰",
        segment: 2,
        trainNumber: "22413",
        trainName: "MAO-NZM RAJD",
        from: "BRC",
        to: "KOTA",
        departure: "00:24",
        arrival: "06:45",
        distance: 527,
        duration: 575,
        waitBefore: 293,
        liveSeatAvailability: "WL/30",
        liveFare: 1305,
        seatAvailable: true,
      },
    ],
    totalTime: 2466,
    totalCost: 2125,
    totalTransfers: 1,
    totalDistance: 2125,
    liveFareTotal: 2125,
    seatProbability: 50,
    safetyScore: 95,
  },
  {
    id: "ROUTE_05",
    category: "BALANCED ⚖️",
    segments: [
      {
        routeId: "ROUTE_05",
        category: "BALANCED ⚖️",
        segment: 1,
        trainNumber: "22476",
        trainName: "CBE BKN AC S",
        from: "PGT",
        to: "BRC",
        departure: "16:20",
        arrival: "19:31",
        distance: 1598,
        duration: 1598,
        waitBefore: 0,
        liveSeatAvailability: "AVAILABLE-025",
        liveFare: 820,
        seatAvailable: false,
      },
      {
        routeId: "ROUTE_05",
        category: "BALANCED ⚖️",
        segment: 2,
        trainNumber: "12247",
        trainName: "BDTS NZM YUV",
        from: "BRC",
        to: "RTM",
        departure: "21:46",
        arrival: "01:05",
        distance: 262,
        duration: 349,
        waitBefore: 135,
        liveSeatAvailability: "WL/18",
        liveFare: 300,
        seatAvailable: true,
      },
      {
        routeId: "ROUTE_05",
        category: "BALANCED ⚖️",
        segment: 3,
        trainNumber: "12247",
        trainName: "BDTS NZM YUV",
        from: "RTM",
        to: "KOTA",
        departure: "01:10",
        arrival: "03:40",
        distance: 265,
        duration: 353,
        waitBefore: 0,
        liveSeatAvailability: "AVAILABLE-008",
        liveFare: 1005,
        seatAvailable: true,
      },
    ],
    totalTime: 2436,
    totalCost: 2125,
    totalTransfers: 2,
    totalDistance: 2125,
    liveFareTotal: 2125,
    seatProbability: 66.67,
    safetyScore: 95,
  },
  {
    id: "ROUTE_06",
    category: "ALTERNATIVE 🔄",
    segments: [
      {
        routeId: "ROUTE_06",
        category: "ALTERNATIVE 🔄",
        segment: 1,
        trainNumber: "12258",
        trainName: "KCVL-YPR EXP",
        from: "PGT",
        to: "CBE",
        departure: "00:15",
        arrival: "01:37",
        distance: 55,
        duration: 87,
        waitBefore: 0,
        liveSeatAvailability: "AVAILABLE-008",
        liveFare: 120,
        seatAvailable: false,
      },
      {
        routeId: "ROUTE_06",
        category: "ALTERNATIVE 🔄",
        segment: 2,
        trainNumber: "12969",
        trainName: "CBE JAIPUR E",
        from: "ED",
        to: "UJN",
        departure: "10:50",
        arrival: "21:25",
        distance: 2058,
        duration: 2129,
        waitBefore: 460,
        liveSeatAvailability: "AVAILABLE-040",
        liveFare: 1420,
        seatAvailable: true,
      },
      {
        routeId: "ROUTE_06",
        category: "ALTERNATIVE 🔄",
        segment: 3,
        trainNumber: "19021",
        trainName: "BDTS LJN EXP",
        from: "BWM",
        to: "KOTA",
        departure: "01:10",
        arrival: "02:40",
        distance: 100,
        duration: 158,
        waitBefore: 32,
        liveSeatAvailability: "WL/15",
        liveFare: 949,
        seatAvailable: true,
      },
    ],
    totalTime: 3301,
    totalCost: 2489,
    totalTransfers: 7,
    totalDistance: 2213,
    liveFareTotal: 2489,
    seatProbability: 75,
    safetyScore: 70,
  },
];

export const formatDuration = (minutes: number): string => {
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
};

export const formatCost = (cost: number): string => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(cost);
};

export const getCategoryBase = (category: string): string => {
  const parts = category.split(/\s+/);
  const first = parts[0]?.split('#')[0] ?? '';
  if (/^\d+$/.test(first) && parts.length >= 2) return parts.slice(0, 2).join(' ');
  return first.replace(/[^A-Za-z0-9]/g, '') || category;
};

const availabilityPriority: Record<AvailabilityState, number> = {
  available: 3,
  waiting: 2,
  "not-available": 1,
  unknown: 0,
};

export interface AvailabilitySummary {
  label: string;
  state: AvailabilityState;
}

/**
 * Format availability for display: never show raw JSON/list.
 * If value looks like a list of objects (e.g. [{'status':'AVAILABLE-0001'},...]), extract first status.
 */
export function formatAvailabilityForDisplay(availability: string | undefined): string {
  if (!availability || typeof availability !== "string") return "Check at booking";
  const s = availability.trim();
  if (!s) return "Check at booking";
  if (s.length <= 40 && !s.startsWith("[") && !s.startsWith("{")) return s;
  try {
    const parsed = JSON.parse(s) as unknown;
    if (Array.isArray(parsed) && parsed.length > 0) {
      const first = parsed[0] as Record<string, unknown>;
      if (first && typeof first.status === "string") return first.status;
    }
  } catch {
    // not JSON
  }
  return "Check at booking";
}

export const getSeatAvailabilityState = (availability?: string): AvailabilityState => {
  const display = formatAvailabilityForDisplay(availability);
  if (!display || display === "Check at booking") return "unknown";
  const normalized = display.toUpperCase();
  if (normalized.startsWith("AVAILABLE")) return "available";
  if (normalized.includes("WL") || normalized.includes("WAIT")) return "waiting";
  if (normalized.includes("NOT")) return "not-available";
  return "unknown";
};

export const getAvailabilityBadgeClasses = (state: AvailabilityState): string => {
  switch (state) {
    case "available":
      return "bg-emerald-50 border-emerald-200 text-emerald-800";
    case "waiting":
      return "bg-amber-50 border-amber-200 text-amber-800";
    case "not-available":
      return "bg-red-50 border-red-200 text-red-800";
    default:
      return "bg-secondary/20 border-border text-muted-foreground";
  }
};

export const formatLiveFare = (fare: number): string => {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: fare % 1 === 0 ? 0 : 2,
  }).format(fare);
};

export const summarizeAvailability = (segments: RouteSegment[]): AvailabilitySummary => {
  if (!segments.length) {
    return { label: "Check at booking", state: "unknown" };
  }

  return segments.reduce<AvailabilitySummary>((acc, segment) => {
    const state = getSeatAvailabilityState(segment.liveSeatAvailability);
    if (availabilityPriority[state] > availabilityPriority[acc.state]) {
      return { label: formatAvailabilityForDisplay(segment.liveSeatAvailability), state };
    }
    return acc;
  }, { label: "Check at booking", state: "unknown" });
};

interface ApiSegment {
  live_seat_availability?: string;
  liveSeatAvailability?: string;
  seat_availability?: string;
  live_fare?: number | string;
  liveFare?: number | string;
  fare?: number | string;
  train_no: string;
  train_name: string;
  from: string;
  to: string;
  departure: string;
  arrival: string;
  distance: number;
  duration_min: number;
  wait_min: number;
}

interface ApiRoute {
  route_id: string;
  category: string;
  segments: ApiSegment[];
  objectives: {
    time: number;
    cost: number;
    transfers: number;
    distance: number;
    seat_prob: number;
    safety_score: number;
  };
}

export const mapApiRouteToRoute = (apiRoute: ApiRoute): Route => {
  const mappedSegments = apiRoute.segments.map((seg: ApiSegment, idx: number) => {
    const availability = seg.live_seat_availability || seg.liveSeatAvailability || seg.seat_availability || "UNKNOWN";
    const fareValue = seg.live_fare ?? seg.liveFare ?? seg.fare ?? 0;
    const liveFare = typeof fareValue === "number"
      ? fareValue
      : Number.parseFloat(String(fareValue)) || 0;
    return {
      routeId: apiRoute.route_id,
      category: apiRoute.category,
      segment: idx + 1,
      trainNumber: seg.train_no,
      trainName: seg.train_name,
      from: seg.from,
      to: seg.to,
      departure: seg.departure,
      arrival: seg.arrival,
      distance: seg.distance,
      duration: seg.duration_min,
      waitBefore: seg.wait_min,
      liveSeatAvailability: availability,
      liveFare,
      seatAvailable: availability.toUpperCase().startsWith("AVAILABLE"),
    };
  });

  const liveFareTotal = mappedSegments.reduce<number>((sum: number, segment) => sum + (segment.liveFare || 0), 0);

  return {
    id: apiRoute.route_id,
    category: apiRoute.category,
    segments: mappedSegments,
    totalTime: apiRoute.objectives.time,
    totalCost: apiRoute.objectives.cost,
    totalTransfers: apiRoute.objectives.transfers,
    totalDistance: apiRoute.objectives.distance,
    liveFareTotal,
    seatProbability: apiRoute.objectives.seat_prob,
    safetyScore: apiRoute.objectives.safety_score,
  };
};
