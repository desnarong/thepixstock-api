#!/bin/bash
# ThePixStock .NET 8 API Project Setup
# Creates complete project structure and initial code

set -e

echo "============================================"
echo "Creating ThePixStock .NET 8 API Project"
echo "============================================"

# Create project directory
mkdir -p ~/ThePixStock
cd ~/ThePixStock

# Create solution
echo "1. Creating solution structure..."
dotnet new sln -n ThePixStock

# Create projects
dotnet new webapi -n ThePixStock.API -f net8.0 -o src/ThePixStock.API
dotnet new classlib -n ThePixStock.Core -f net8.0 -o src/ThePixStock.Core
dotnet new classlib -n ThePixStock.Infrastructure -f net8.0 -o src/ThePixStock.Infrastructure
dotnet new classlib -n ThePixStock.Shared -f net8.0 -o src/ThePixStock.Shared

# Create test projects
dotnet new xunit -n ThePixStock.UnitTests -f net8.0 -o tests/ThePixStock.UnitTests
dotnet new xunit -n ThePixStock.IntegrationTests -f net8.0 -o tests/ThePixStock.IntegrationTests

# Add projects to solution
echo "2. Adding projects to solution..."
dotnet sln add src/ThePixStock.API/ThePixStock.API.csproj
dotnet sln add src/ThePixStock.Core/ThePixStock.Core.csproj
dotnet sln add src/ThePixStock.Infrastructure/ThePixStock.Infrastructure.csproj
dotnet sln add src/ThePixStock.Shared/ThePixStock.Shared.csproj
dotnet sln add tests/ThePixStock.UnitTests/ThePixStock.UnitTests.csproj
dotnet sln add tests/ThePixStock.IntegrationTests/ThePixStock.IntegrationTests.csproj

# Add project references
echo "3. Setting up project references..."
dotnet add src/ThePixStock.API reference src/ThePixStock.Core
dotnet add src/ThePixStock.API reference src/ThePixStock.Infrastructure
dotnet add src/ThePixStock.API reference src/ThePixStock.Shared
dotnet add src/ThePixStock.Infrastructure reference src/ThePixStock.Core
dotnet add src/ThePixStock.Infrastructure reference src/ThePixStock.Shared
dotnet add src/ThePixStock.Core reference src/ThePixStock.Shared
dotnet add tests/ThePixStock.UnitTests reference src/ThePixStock.Core
dotnet add tests/ThePixStock.UnitTests reference src/ThePixStock.Infrastructure
dotnet add tests/ThePixStock.IntegrationTests reference src/ThePixStock.API

# Install NuGet packages
echo "4. Installing NuGet packages..."

# API Project packages
cd src/ThePixStock.API
dotnet add package Microsoft.AspNetCore.Authentication.JwtBearer --version 8.0.0
dotnet add package Swashbuckle.AspNetCore --version 6.5.0
dotnet add package Serilog.AspNetCore --version 8.0.0
dotnet add package Serilog.Sinks.File --version 5.0.0
dotnet add package Serilog.Sinks.Console --version 5.0.0
dotnet add package Microsoft.AspNetCore.SignalR --version 1.1.0
dotnet add package Microsoft.EntityFrameworkCore.Design --version 8.0.0

# Infrastructure Project packages
cd ../ThePixStock.Infrastructure
dotnet add package Npgsql.EntityFrameworkCore.PostgreSQL --version 8.0.0
dotnet add package Microsoft.EntityFrameworkCore.Tools --version 8.0.0
dotnet add package StackExchange.Redis --version 2.7.4
dotnet add package Minio --version 6.0.1
dotnet add package BCrypt.Net-Next --version 4.0.3
dotnet add package MailKit --version 4.3.0

# Core Project packages
cd ../ThePixStock.Core
dotnet add package FluentValidation --version 11.8.1
dotnet add package AutoMapper --version 12.0.1
dotnet add package MediatR --version 12.2.0

# Shared Project packages
cd ../ThePixStock.Shared
dotnet add package Newtonsoft.Json --version 13.0.3

cd ~/ThePixStock

# Create directory structure
echo "5. Creating directory structure..."
mkdir -p src/ThePixStock.Core/{Entities,Interfaces,Services,Specifications,Exceptions}
mkdir -p src/ThePixStock.Infrastructure/{Data,Repositories,Services,Migrations}
mkdir -p src/ThePixStock.Shared/{DTOs,Constants,Utils,Extensions}
mkdir -p src/ThePixStock.API/{Controllers,Middleware,Filters,Hubs,Extensions}

# Create Core Entities
echo "6. Creating Core Entities..."

# User Entity
cat > src/ThePixStock.Core/Entities/User.cs <<'EOF'
using System;
using System.Collections.Generic;

namespace ThePixStock.Core.Entities
{
    public class User
    {
        public int Id { get; set; }
        public string Email { get; set; } = string.Empty;
        public string PasswordHash { get; set; } = string.Empty;
        public UserRole Role { get; set; }
        public string FirstName { get; set; } = string.Empty;
        public string LastName { get; set; } = string.Empty;
        public string? Phone { get; set; }
        public bool IsActive { get; set; } = true;
        public bool EmailVerified { get; set; } = false;
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        public DateTime? LastLogin { get; set; }
        
        public virtual ICollection<Event> CreatedEvents { get; set; } = new List<Event>();
        public virtual ICollection<Photo> Photos { get; set; } = new List<Photo>();
        public virtual ICollection<Order> Orders { get; set; } = new List<Order>();
    }
    
    public enum UserRole
    {
        Admin,
        Photographer,
        Customer
    }
}
EOF

# Event Entity
cat > src/ThePixStock.Core/Entities/Event.cs <<'EOF'
using System;
using System.Collections.Generic;

namespace ThePixStock.Core.Entities
{
    public class Event
    {
        public int Id { get; set; }
        public string Name { get; set; } = string.Empty;
        public string? Description { get; set; }
        public DateTime? EventDate { get; set; }
        public string? Location { get; set; }
        public string? Venue { get; set; }
        public EventStatus Status { get; set; } = EventStatus.Planning;
        public bool SalesEnabled { get; set; } = false;
        public DateTime? SalesStartDate { get; set; }
        public DateTime? SalesEndDate { get; set; }
        public int TotalPhotos { get; set; } = 0;
        public int ApprovedPhotos { get; set; } = 0;
        public int CreatedById { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        
        public virtual User Creator { get; set; } = null!;
        public virtual ICollection<Photo> Photos { get; set; } = new List<Photo>();
        public virtual ICollection<EventPricing> Pricing { get; set; } = new List<EventPricing>();
        public virtual ICollection<Order> Orders { get; set; } = new List<Order>();
    }
    
    public enum EventStatus
    {
        Planning,
        Shooting,
        Uploading,
        Processing,
        Reviewing,
        Live,
        Closed
    }
}
EOF

# Photo Entity
cat > src/ThePixStock.Core/Entities/Photo.cs <<'EOF'
using System;
using System.Collections.Generic;

namespace ThePixStock.Core.Entities
{
    public class Photo
    {
        public int Id { get; set; }
        public int EventId { get; set; }
        public int PhotographerId { get; set; }
        public string OriginalFilename { get; set; } = string.Empty;
        public string Filename { get; set; } = string.Empty;
        public string FilePath { get; set; } = string.Empty;
        public long FileSize { get; set; }
        public string MimeType { get; set; } = string.Empty;
        public int? Width { get; set; }
        public int? Height { get; set; }
        public ProcessingStatus ProcessingStatus { get; set; } = ProcessingStatus.Pending;
        public ProcessingStatus ThumbnailStatus { get; set; } = ProcessingStatus.Pending;
        public ProcessingStatus WatermarkStatus { get; set; } = ProcessingStatus.Pending;
        public ProcessingStatus FaceDetectionStatus { get; set; } = ProcessingStatus.Pending;
        public ApprovalStatus ApprovalStatus { get; set; } = ApprovalStatus.Pending;
        public DateTime UploadedAt { get; set; }
        public DateTime? ProcessedAt { get; set; }
        public DateTime? ApprovedAt { get; set; }
        
        public virtual Event Event { get; set; } = null!;
        public virtual User Photographer { get; set; } = null!;
        public virtual ICollection<PhotoFace> Faces { get; set; } = new List<PhotoFace>();
    }
    
    public enum ProcessingStatus
    {
        Pending,
        Processing,
        Completed,
        Failed
    }
    
    public enum ApprovalStatus
    {
        Pending,
        Approved,
        Rejected
    }
}
EOF

# Order Entity
cat > src/ThePixStock.Core/Entities/Order.cs <<'EOF'
using System;
using System.Collections.Generic;

namespace ThePixStock.Core.Entities
{
    public class Order
    {
        public int Id { get; set; }
        public string OrderNumber { get; set; } = string.Empty;
        public int CustomerId { get; set; }
        public int EventId { get; set; }
        public int PackageId { get; set; }
        public decimal TotalAmount { get; set; }
        public OrderStatus Status { get; set; } = OrderStatus.Pending;
        public PaymentStatus PaymentStatus { get; set; } = PaymentStatus.Pending;
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        
        public virtual User Customer { get; set; } = null!;
        public virtual Event Event { get; set; } = null!;
        public virtual EventPricing Package { get; set; } = null!;
        public virtual ICollection<OrderItem> Items { get; set; } = new List<OrderItem>();
        public virtual Payment? Payment { get; set; }
    }
    
    public enum OrderStatus
    {
        Pending,
        Processing,
        Completed,
        Cancelled
    }
    
    public enum PaymentStatus
    {
        Pending,
        Processing,
        Completed,
        Failed,
        Refunded
    }
}
EOF

# Additional Entities
cat > src/ThePixStock.Core/Entities/EventPricing.cs <<'EOF'
namespace ThePixStock.Core.Entities
{
    public class EventPricing
    {
        public int Id { get; set; }
        public int EventId { get; set; }
        public string PackageType { get; set; } = string.Empty;
        public string PackageName { get; set; } = string.Empty;
        public int? PhotoCount { get; set; }
        public decimal Price { get; set; }
        public bool IsActive { get; set; } = true;
        public DateTime CreatedAt { get; set; }
        
        public virtual Event Event { get; set; } = null!;
    }
}
EOF

cat > src/ThePixStock.Core/Entities/PhotoFace.cs <<'EOF'
namespace ThePixStock.Core.Entities
{
    public class PhotoFace
    {
        public int Id { get; set; }
        public int PhotoId { get; set; }
        public byte[] Encoding { get; set; } = Array.Empty<byte>();
        public string BoundingBox { get; set; } = string.Empty;
        public decimal Confidence { get; set; }
        public decimal QualityScore { get; set; }
        public DateTime CreatedAt { get; set; }
        
        public virtual Photo Photo { get; set; } = null!;
    }
}
EOF

cat > src/ThePixStock.Core/Entities/Payment.cs <<'EOF'
namespace ThePixStock.Core.Entities
{
    public class Payment
    {
        public int Id { get; set; }
        public int OrderId { get; set; }
        public string? TransactionId { get; set; }
        public decimal Amount { get; set; }
        public PaymentStatus Status { get; set; } = PaymentStatus.Pending;
        public string? Gateway { get; set; }
        public string? PaymentMethod { get; set; }
        public string? ReferenceNumber { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime? ProcessedAt { get; set; }
        public DateTime? ExpireAt { get; set; }
        
        public virtual Order Order { get; set; } = null!;
    }
}
EOF

cat > src/ThePixStock.Core/Entities/OrderItem.cs <<'EOF'
namespace ThePixStock.Core.Entities
{
    public class OrderItem
    {
        public int Id { get; set; }
        public int OrderId { get; set; }
        public int PhotoId { get; set; }
        public decimal Price { get; set; }
        
        public virtual Order Order { get; set; } = null!;
        public virtual Photo Photo { get; set; } = null!;
    }
}
EOF

# Create DbContext
echo "7. Creating Database Context..."
cat > src/ThePixStock.Infrastructure/Data/ApplicationDbContext.cs <<'EOF'
using Microsoft.EntityFrameworkCore;
using ThePixStock.Core.Entities;

namespace ThePixStock.Infrastructure.Data
{
    public class ApplicationDbContext : DbContext
    {
        public ApplicationDbContext(DbContextOptions<ApplicationDbContext> options)
            : base(options)
        {
        }
        
        public DbSet<User> Users { get; set; }
        public DbSet<Event> Events { get; set; }
        public DbSet<Photo> Photos { get; set; }
        public DbSet<PhotoFace> PhotoFaces { get; set; }
        public DbSet<EventPricing> EventPricing { get; set; }
        public DbSet<Order> Orders { get; set; }
        public DbSet<OrderItem> OrderItems { get; set; }
        public DbSet<Payment> Payments { get; set; }
        
        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);
            
            // User configuration
            modelBuilder.Entity<User>(entity =>
            {
                entity.HasIndex(e => e.Email).IsUnique();
                entity.Property(e => e.Email).IsRequired().HasMaxLength(255);
                entity.Property(e => e.PasswordHash).IsRequired();
                entity.Property(e => e.Role).HasConversion<string>();
            });
            
            // Event configuration
            modelBuilder.Entity<Event>(entity =>
            {
                entity.Property(e => e.Name).IsRequired().HasMaxLength(255);
                entity.Property(e => e.Status).HasConversion<string>();
                entity.HasOne(e => e.Creator)
                    .WithMany(u => u.CreatedEvents)
                    .HasForeignKey(e => e.CreatedById);
            });
            
            // Photo configuration
            modelBuilder.Entity<Photo>(entity =>
            {
                entity.Property(e => e.Filename).IsRequired();
                entity.Property(e => e.ProcessingStatus).HasConversion<string>();
                entity.Property(e => e.ApprovalStatus).HasConversion<string>();
                entity.HasIndex(e => e.EventId);
                entity.HasIndex(e => e.PhotographerId);
            });
            
            // Order configuration
            modelBuilder.Entity<Order>(entity =>
            {
                entity.Property(e => e.OrderNumber).IsRequired();
                entity.HasIndex(e => e.OrderNumber).IsUnique();
                entity.Property(e => e.Status).HasConversion<string>();
                entity.Property(e => e.PaymentStatus).HasConversion<string>();
                entity.Property(e => e.TotalAmount).HasPrecision(10, 2);
            });
            
            // Payment configuration
            modelBuilder.Entity<Payment>(entity =>
            {
                entity.Property(e => e.Amount).HasPrecision(10, 2);
                entity.Property(e => e.Status).HasConversion<string>();
                entity.HasIndex(e => e.TransactionId).IsUnique();
            });
            
            // EventPricing configuration
            modelBuilder.Entity<EventPricing>(entity =>
            {
                entity.Property(e => e.Price).HasPrecision(10, 2);
            });
        }
    }
}
EOF

# Create Program.cs
echo "8. Creating Program.cs..."
cat > src/ThePixStock.API/Program.cs <<'EOF'
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using Microsoft.OpenApi.Models;
using Serilog;
using StackExchange.Redis;
using System.Text;
using ThePixStock.Infrastructure.Data;

var builder = WebApplication.CreateBuilder(args);

// Configure Serilog
Log.Logger = new LoggerConfiguration()
    .ReadFrom.Configuration(builder.Configuration)
    .Enrich.FromLogContext()
    .WriteTo.Console()
    .WriteTo.File("logs/log-.txt", rollingInterval: RollingInterval.Day)
    .CreateLogger();

builder.Host.UseSerilog();

// Add services
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new OpenApiInfo 
    { 
        Title = "ThePixStock API", 
        Version = "v1",
        Description = "Event Photo Sales Platform API"
    });
    
    c.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
    {
        Description = "JWT Authorization header using the Bearer scheme",
        Name = "Authorization",
        In = ParameterLocation.Header,
        Type = SecuritySchemeType.ApiKey,
        Scheme = "Bearer"
    });
    
    c.AddSecurityRequirement(new OpenApiSecurityRequirement
    {
        {
            new OpenApiSecurityScheme
            {
                Reference = new OpenApiReference
                {
                    Type = ReferenceType.SecurityScheme,
                    Id = "Bearer"
                }
            },
            Array.Empty<string>()
        }
    });
});

// Configure Database
builder.Services.AddDbContext<ApplicationDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection")));

// Configure Redis
builder.Services.AddSingleton<IConnectionMultiplexer>(sp =>
{
    var configuration = ConfigurationOptions.Parse(
        builder.Configuration.GetConnectionString("Redis") ?? "localhost:6379", true);
    configuration.Password = builder.Configuration["Redis:Password"];
    return ConnectionMultiplexer.Connect(configuration);
});

// Configure JWT Authentication
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = builder.Configuration["Jwt:Issuer"],
            ValidAudience = builder.Configuration["Jwt:Audience"],
            IssuerSigningKey = new SymmetricSecurityKey(
                Encoding.UTF8.GetBytes(builder.Configuration["Jwt:SecretKey"] ?? ""))
        };
    });

// Configure Authorization
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("AdminOnly", policy => policy.RequireRole("Admin"));
    options.AddPolicy("PhotographerOnly", policy => policy.RequireRole("Photographer"));
    options.AddPolicy("CustomerOnly", policy => policy.RequireRole("Customer"));
});

// Configure CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowWebApp",
        builder => builder
            .WithOrigins("https://thepixstock.com", "http://localhost:3000")
            .AllowAnyMethod()
            .AllowAnyHeader()
            .AllowCredentials());
});

// Configure SignalR
builder.Services.AddSignalR();

// Configure AutoMapper
builder.Services.AddAutoMapper(AppDomain.CurrentDomain.GetAssemblies());

var app = builder.Build();

// Configure middleware pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.UseSerilogRequestLogging();
app.UseCors("AllowWebApp");
app.UseAuthentication();
app.UseAuthorization();
app.MapControllers();

// Health check endpoint
app.MapGet("/health", () => Results.Ok(new { status = "healthy", timestamp = DateTime.UtcNow }));

// Run database migrations
using (var scope = app.Services.CreateScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    dbContext.Database.Migrate();
}

app.Run();
EOF

# Create appsettings.json
echo "9. Creating appsettings.json..."
cat > src/ThePixStock.API/appsettings.json <<'EOF'
{
  "ConnectionStrings": {
    "DefaultConnection": "Host=localhost;Database=thepixstock_db;Username=thepixstock;Password=SecurePassword123!",
    "Redis": "localhost:6379"
  },
  "Jwt": {
    "SecretKey": "ThisIsAVerySecureSecretKeyForJWTTokenGeneration2024!",
    "Issuer": "https://api.thepixstock.com",
    "Audience": "https://thepixstock.com",
    "ExpiryMinutes": 30
  },
  "PayNoi": {
    "BaseUrl": "https://paynoi.com/ppay_api",
    "ApiKey": "your_api_key_here",
    "KeyId": "your_key_id",
    "Account": "your_account"
  },
  "MinIO": {
    "Endpoint": "localhost:9000",
    "AccessKey": "minioadmin",
    "SecretKey": "SecureMinioPassword123!",
    "BucketName": "thepixstock",
    "UseSSL": false
  },
  "Redis": {
    "Password": "YourRedisPassword123!"
  },
  "Serilog": {
    "MinimumLevel": {
      "Default": "Information",
      "Override": {
        "Microsoft": "Warning",
        "System": "Warning"
      }
    }
  },
  "AllowedHosts": "*"
}
EOF

# Create initial migration
echo "10. Creating initial database migration..."
cd src/ThePixStock.API
dotnet ef migrations add InitialCreate -p ../ThePixStock.Infrastructure -s . -c ApplicationDbContext

# Build the solution
echo "11. Building the solution..."
cd ~/ThePixStock
dotnet build

# Create deployment script
echo "12. Creating deployment script..."
cat > deploy.sh <<'EOF'
#!/bin/bash
# ThePixStock API Deployment Script

set -e

echo "Deploying ThePixStock API..."

# Build in Release mode
dotnet publish src/ThePixStock.API/ThePixStock.API.csproj -c Release -o ./publish

# Stop existing service
sudo systemctl stop thepixstock-api || true

# Copy files to deployment directory
sudo cp -r ./publish/* /var/www/thepixstock-api/

# Set permissions
sudo chown -R thepixstock:thepixstock /var/www/thepixstock-api

# Create systemd service
sudo cat > /etc/systemd/system/thepixstock-api.service <<'SERVICE'
[Unit]
Description=ThePixStock API
After=network.target

[Service]
Type=notify
User=thepixstock
Group=thepixstock
WorkingDirectory=/var/www/thepixstock-api
ExecStart=/usr/bin/dotnet /var/www/thepixstock-api/ThePixStock.API.dll
Restart=always
RestartSec=10
KillSignal=SIGINT
SyslogIdentifier=thepixstock-api
Environment=ASPNETCORE_ENVIRONMENT=Production
Environment=DOTNET_PRINT_TELEMETRY_MESSAGE=false

[Install]
WantedBy=multi-user.target
SERVICE

# Reload systemd and start service
sudo systemctl daemon-reload
sudo systemctl enable thepixstock-api
sudo systemctl start thepixstock-api

echo "Deployment complete!"
echo "Check status with: sudo systemctl status thepixstock-api"
EOF

chmod +x deploy.sh

echo "============================================"
echo "ThePixStock .NET 8 API Project Created!"
echo "============================================"
echo ""
echo "Project structure created at: ~/ThePixStock"
echo ""
echo "Next steps:"
echo "1. Update connection strings in appsettings.json"
echo "2. Update PayNoi API credentials"
echo "3. Run migrations: dotnet ef database update"
echo "4. Run locally: dotnet run --project src/ThePixStock.API"
echo "5. Deploy: ./deploy.sh"
echo ""
echo "API will be available at:"
echo "- Development: http://localhost:5000"
echo "- Swagger UI: http://localhost:5000/swagger"
echo "============================================"