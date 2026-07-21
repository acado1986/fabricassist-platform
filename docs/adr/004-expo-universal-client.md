# ADR-004: Use an Expo universal client

- **Status:** Accepted
- **Date:** 2026-07-20

## Context

FabricAssist must serve Android, iOS, and authenticated web users while sharing
business-facing presentation and validation where practical.

## Decision

Use one strict-TypeScript Expo/React Native application named
`fabricassist-app`, with small platform-specific adapters for camera, files, and
secure sessions. Defer a separate web framework until measured needs justify it.

## Consequences

Shared behavior stays consistent across platforms. Phase 3 owns Expo and pnpm
initialization; Phase 1 contains no frontend scaffold.
