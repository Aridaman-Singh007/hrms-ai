# System Context — HRMS AI

## Purpose

AI-powered resume scoring and ranking system.

## Flow

JD → Parse → Resume → Parse → Score → Rank → Display

## Key Services

* JD Parser
* Resume Parser
* Scoring Engine

## Architecture Style

REST + Async Queue

## Stack

FastAPI, PostgreSQL, Redis, Qdrant, OpenAI
