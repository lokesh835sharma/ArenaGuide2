import type { Config } from "@netlify/functions";
import stadiumData from "../../src/data/stadium.json" with { type: "json" };
import facilitiesData from "../../src/data/facilities.json" with { type: "json" };

// Kept in sync with src/models/schemas.py (NavigationGoal, Locale, MobilityRequirement).
const INTENTS = [
  "restroom",
  "gate",
  "seat",
  "exit",
  "first_aid",
  "concession",
  "guest_services",
  "water",
  "sensory_room",
  "merchandise",
];
const LANGUAGES = ["en", "es", "fr"];
const ACCESSIBILITY_NEEDS = ["wheelchair", "visual", "hearing", "none"];

export default async () => {
  const { stadium, zones } = stadiumData;

  return Response.json({
    stadium: {
      name: stadium.name,
      fifa_name: stadium.fifa_name,
      city: stadium.city,
      capacity: stadium.capacity,
    },
    zones: zones.map((z) => ({ id: z.id, name: z.name, type: z.type, level: z.level })),
    facilities: facilitiesData.facilities.map((f) => ({
      id: f.id,
      name: f.name,
      type: f.type,
      zone: f.zone,
      accessible: f.accessible,
      landmark: f.landmark ?? null,
    })),
    intents: INTENTS,
    languages: LANGUAGES,
    accessibility_needs: ACCESSIBILITY_NEEDS,
  });
};

export const config: Config = {
  path: "/api/stadium",
};
