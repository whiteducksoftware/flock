---
name: dhh-rails-style
description: Write Ruby on Rails code in DHH's 37signals style — fat models, thin controllers, Hotwire over SPA, convention over configuration.
license: MIT
# No flock: block — pure prose, compiles as instructions only
---

## Principles

1. **Fat models, thin controllers.** Business logic belongs in the model layer.
2. **REST resources over bespoke endpoints.** Seven actions. That's it.
3. **Hotwire over SPA.** Turbo frames, Stimulus, no React.
4. **Current attributes over thread locals.** Use `Current.user`, not `Thread.current[:user]`.
5. **Convention over configuration.** Don't configure what Rails already knows.

## How to apply

When generating Rails code, prefer:
- `ActiveRecord::Base` inheritance without STI unless forced
- `has_many :through` over join tables with explicit models
- Integer primary keys unless UUIDs are required for security
- `concerns/` for shared behavior across models
- Plain Ruby objects over service layers until a service layer is genuinely needed
- `ActionView::Helpers` for formatting, not decorator gems

## How not to apply

- Don't reach for `ServiceObjects` / `Interactor` / `Trailblazer` on day one
- Don't replace `form_with` with React forms
- Don't use `Sidekiq` where `ActiveJob` will do
- Don't invent new abstractions to "decouple" Rails — embrace the monolith
