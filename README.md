# Property Operations Manager

> Current status: Technical design and project setup.

## Overview

Property Operations Manager is a web application for organising a small property portfolio and the day-to-day operational work associated with it.

It is intended to bring properties, contacts, issues, tasks, events, notes and scheduling information into one lightweight system without the overhead of enterprise property-management software.

## Target user

The primary user is an individual managing approximately 5–50 properties.

Version 1.0 is manager-facing. Other people involved in property operations, including landlords, tenants, contractors and agents, are represented as Contacts rather than application users.

## Planned V1 scope

Version 1.0 is planned to provide:

- A public-facing product website
- Account registration and authentication
- Property portfolio management
- Contact and property-role management
- Creation and management of Issues, Tasks and Events
- Calendar-based scheduling of Tasks and Events
- Contextual Notes and NotesBoards
- A portfolio dashboard and calendar
- Read-only access to historical operational records

## Technology

- Python 3.14
- Django 5.2.17 LTS
- PostgreSQL 18
- Server-rendered HTML and CSS with Bootstrap

## Development approach

This is a personal portfolio and learning project intended to strengthen practical skills in system design, relational database modelling, Django development, testing and deployment.

Development follows a structured but lightweight software-development lifecycle: requirements analysis, domain modelling, technical design, incremental implementation, continuous testing and iteration. The process emphasises useful engineering discipline without unnecessary ceremony.

## Project status

Requirements and domain analysis are substantially complete. Technical design and application setup are now underway.
