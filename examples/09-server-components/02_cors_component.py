"""
Advanced CORS Configuration Examples

This example demonstrates the enhanced CORS component capabilities:
1. Global CORS settings
2. Origin regex patterns
3. Route-specific CORS overrides
4. Exposed headers configuration
5. Max age and credentials control
"""

from flock import Flock
from flock.components.server import (
    CORSComponent,
    CORSComponentConfig,
    RouteSpecificCORSConfig,
)


# Example 1: Basic global CORS configuration
def example_basic_cors():
    """Basic CORS with specific origins and methods."""
    flock = Flock()

    cors_component = CORSComponent(
        config=CORSComponentConfig(
            allow_origins=["https://example.com", "https://app.example.com"],
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Content-Type", "Authorization"],
            allow_credentials=True,
            max_age=3600,  # Cache preflight for 1 hour
        )
    )

    return flock, cors_component


# Example 2: CORS with origin regex pattern
def example_regex_cors():
    """Allow all subdomains of example.com using regex."""
    flock = Flock()

    cors_component = CORSComponent(
        config=CORSComponentConfig(
            # Allow any subdomain of example.com
            allow_origin_regex=r"https://.*\.example\.com",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "X-RateLimit-Remaining"],
            max_age=7200,  # Cache preflight for 2 hours
        )
    )

    return flock, cors_component


# Example 3: Route-specific CORS overrides
def example_route_specific_cors():
    """Different CORS policies for different routes."""
    flock = Flock()

    cors_component = CORSComponent(
        config=CORSComponentConfig(
            # Default global settings - restrictive
            allow_origins=["https://example.com"],
            allow_methods=["GET", "POST"],
            allow_credentials=True,
            # Route-specific overrides
            route_configs=[
                # Public API - allow all origins, no credentials
                RouteSpecificCORSConfig(
                    path_pattern=r"^/api/public/.*",
                    allow_origins=["*"],
                    allow_methods=["GET", "POST", "OPTIONS"],
                    allow_credentials=False,
                    max_age=86400,  # 24 hours
                ),
                # Admin API - very restrictive
                RouteSpecificCORSConfig(
                    path_pattern=r"^/api/admin/.*",
                    allow_origins=["https://admin.example.com"],
                    allow_methods=["GET", "POST", "PUT", "DELETE"],
                    allow_credentials=True,
                    max_age=600,  # 10 minutes
                ),
                # Webhooks - specific external services
                RouteSpecificCORSConfig(
                    path_pattern=r"^/webhooks/.*",
                    allow_origins=[
                        "https://github.com",
                        "https://stripe.com",
                    ],
                    allow_methods=["POST"],
                    allow_credentials=False,
                    max_age=3600,
                ),
            ],
        )
    )

    return flock, cors_component


# Example 4: Development vs Production CORS
def example_environment_based_cors(is_production: bool = False):
    """Different CORS settings for development vs production."""
    flock = Flock()

    if is_production:
        # Production: strict CORS
        cors_component = CORSComponent(
            config=CORSComponentConfig(
                allow_origins=[
                    "https://app.example.com",
                    "https://www.example.com",
                ],
                allow_methods=["GET", "POST", "PUT", "DELETE"],
                allow_headers=["Content-Type", "Authorization"],
                expose_headers=["X-Request-ID"],
                allow_credentials=True,
                max_age=3600,
            )
        )
    else:
        # Development: permissive CORS
        cors_component = CORSComponent(
            config=CORSComponentConfig(
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
                allow_credentials=False,
                max_age=600,
            )
        )

    return flock, cors_component


# Example 5: Complex multi-tenant CORS
def example_multi_tenant_cors():
    """Different CORS policies for different tenant endpoints."""
    flock = Flock()

    cors_component = CORSComponent(
        config=CORSComponentConfig(
            # Default: no access
            allow_origins=[],
            allow_methods=["GET"],
            allow_credentials=False,
            route_configs=[
                # Tenant A endpoints
                RouteSpecificCORSConfig(
                    path_pattern=r"^/tenant/tenant-a/.*",
                    allow_origins=["https://tenant-a.example.com"],
                    allow_methods=["GET", "POST", "PUT", "DELETE"],
                    allow_credentials=True,
                    expose_headers=["X-Tenant-ID", "X-Request-ID"],
                ),
                # Tenant B endpoints
                RouteSpecificCORSConfig(
                    path_pattern=r"^/tenant/tenant-b/.*",
                    allow_origin_regex=r"https://.*\.tenant-b\.example\.com",
                    allow_methods=["GET", "POST", "PUT", "DELETE"],
                    allow_credentials=True,
                    expose_headers=["X-Tenant-ID", "X-Request-ID"],
                ),
                # Public documentation - accessible to all
                RouteSpecificCORSConfig(
                    path_pattern=r"^/docs/.*",
                    allow_origins=["*"],
                    allow_methods=["GET"],
                    allow_credentials=False,
                ),
            ],
        )
    )

    return flock, cors_component


# Example 6: API Gateway pattern with CORS
def example_api_gateway_cors():
    """CORS configuration for an API gateway pattern."""
    flock = Flock()

    cors_component = CORSComponent(
        config=CORSComponentConfig(
            # Default for authenticated endpoints
            allow_origins=["https://app.example.com"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"],
            route_configs=[
                # Health check - open to monitoring services
                RouteSpecificCORSConfig(
                    path_pattern=r"^/health$",
                    allow_origins=["*"],
                    allow_methods=["GET"],
                    allow_credentials=False,
                ),
                # Metrics - restricted to monitoring domain
                RouteSpecificCORSConfig(
                    path_pattern=r"^/metrics$",
                    allow_origins=["https://monitoring.example.com"],
                    allow_methods=["GET"],
                    allow_credentials=True,
                ),
                # GraphQL endpoint - specific origins
                RouteSpecificCORSConfig(
                    path_pattern=r"^/graphql$",
                    allow_origins=[
                        "https://app.example.com",
                        "https://playground.example.com",
                    ],
                    allow_methods=["POST", "GET"],
                    allow_headers=["Content-Type", "Authorization", "X-Apollo-Tracing"],
                    expose_headers=["X-Apollo-Tracing"],
                    allow_credentials=True,
                ),
            ],
        )
    )

    return flock, cors_component


async def main():
    """Run a server with advanced CORS configuration."""
    # Choose an example to run
    flock, cors_component = example_route_specific_cors()

    # Add the component with the builder-pattern.
    # Alternatively: you could also call flock.serve(...,additional_components=[cors])
    flock = flock.add_server_component(cors_component)

    # Start the server with the CORS component
    await flock.serve(
        flock,
        dashboard=True,
        host="0.0.0.0",
        port=8344,
    )


if __name__ == "__main__":
    import asyncio

    print("🔒 Advanced CORS Configuration Examples")
    print("=" * 50)
    print("\nAvailable examples:")
    print("1. Basic CORS - Specific origins and methods")
    print("2. Regex CORS - Pattern-based origin matching")
    print("3. Route-specific CORS - Different policies per route")
    print("4. Environment-based CORS - Dev vs Production")
    print("5. Multi-tenant CORS - Tenant-specific policies")
    print("6. API Gateway CORS - Complex routing patterns")
    print("\nCurrently running: Route-specific CORS example")
    print("Modify the main() function to try different examples.")
    print("=" * 50)

    asyncio.run(main())
