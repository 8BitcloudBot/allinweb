const rawBase = import.meta.env.BASE_URL;
const base = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;

export const SITE = {
  title: "Vincent Hu",
  description: "A passionate developer who loves building things for the web.",
  author: "Vincent Hu",
  email: "17889786156@163.com",
  github: "https://github.com/8BitcloudBot",
  nav: [
    { name: "Blog", path: `${base}blog`, icon: "article" },
    { name: "Projects", path: `${base}projects`, icon: "lightbulb" },
    { name: "ChefMate-RAG", path: `${base}chefmate`, icon: "chefmate" },
    { name: "GraphRAG", path: `${base}chefmate-graphrag`, icon: "chefmate" },
    { name: "Photos", path: `${base}photos`, icon: "image" },
    { name: "About", path: `${base}about`, icon: "user" },
  ],
  social: [
    { name: "GitHub", url: "https://github.com/8BitcloudBot", icon: "github" },
  ],
};
