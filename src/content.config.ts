import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const clouds = defineCollection({
  loader: glob({ pattern: "**/*.mdx", base: "./src/content/clouds" }),
  schema: z.object({
    status: z.enum(["draft", "reviewed"]).default("draft"),
    headquarters: z.string().optional(),
    foundedYear: z.number().int().optional(),
    regions: z.array(z.string()).optional(),
    services: z.array(z.string()).optional(),
    openSource: z.boolean().optional(),
    pricingModel: z.enum(["hourly", "monthly", "usage-based", "subscription", "mixed"]).optional(),
    socials: z
      .object({
        x: z.string().optional(),
        linkedin: z.string().optional(),
        github: z.string().optional(),
        website: z.string().optional(),
      })
      .optional(),
    logo: z.string().optional(),
    tagline: z.string().optional(),
  }),
});

const blog = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/blog" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    publishDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    author: z.string(),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
    heroImage: z.string().optional(),
  }),
});

export const collections = { clouds, blog };
