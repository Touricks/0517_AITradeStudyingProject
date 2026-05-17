// Maps the prototype's page keys (home / assessment / training / review)
// to real router paths, per the information architecture in plan.md.
export const ROUTES = {
  home: "/",
  assessment: "/assessment",
  training: "/training",
  review: "/review",
};

export const KEY_BY_PATH = {
  "/": "home",
  "/assessment": "assessment",
  "/training": "training",
  "/review": "review",
};
