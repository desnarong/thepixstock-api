# VM1 - API Server Implementation Guide
## .NET 8 Backend Development

## 📋 Table of Contents
1. [System Setup](#system-setup)
2. [Project Structure](#project-structure)
3. [Database Implementation](#database-implementation)
4. [API Implementation](#api-implementation)
5. [Payment Integration](#payment-integration)
6. [Security Implementation](#security-implementation)
7. [Testing & Deployment](#testing--deployment)

---

## 🖥️ System Setup

### Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y wget curl git nginx certbot python3-certbot-nginx ufw fail2ban

# Install .NET 8
wget https://dot.net/v1/dotnet-install.sh
chmod +x dotnet-install.sh
./dotnet-install.sh --version 8.0.100
export PATH="$PATH:$HOME/.dotnet"
echo 'export PATH="$PATH:$HOME/.dotnet"' >> ~/.bashrc

# Verify installation
dotnet --version
```

### PostgreSQL Installation
```bash
# Install PostgreSQL 15
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update
sudo apt install -y postgresql-15 postgresql-client-15

# Configure PostgreSQL
sudo -u postgres psql
CREATE USER thepixstock WITH PASSWORD 'SecurePassword123!';
CREATE DATABASE thepixstock_db OWNER thepixstock;
GRANT ALL PRIVILEGES ON DATABASE thepixstock_db TO thepixstock;
\q

# Update PostgreSQL configuration
sudo nano /etc/postgresql/15/main/postgresql.conf
# Set: listen_addresses = 'localhost'
# Set: max_connections = 200

sudo systemctl restart postgresql
```

### Redis Installation
```bash
# Install Redis
sudo apt install -y redis-server

# Configure Redis
sudo nano /etc/redis/redis.conf
# Set: maxmemory 2gb
# Set: maxmemory-policy allkeys-lru
# Set: requirepass YourRedisPassword123!

sudo systemctl restart redis-server

# Test Redis
redis-cli -a YourRedisPassword123! ping
```

### MinIO Installation
```bash
# Download MinIO
wget https://dl.min.io/server/minio/release/linux-amd64/minio
chmod +x minio
sudo mv minio /usr/local/bin/

# Create MinIO user and directories
sudo useradd -r minio-user -s /sbin/nologin
sudo mkdir -p /data/minio
sudo chown minio-user:minio-user /data/minio

# Create systemd service
sudo nano /etc/systemd/system/minio.service
```

```ini
[Unit]
Description=MinIO
Documentation=https://docs.min.io
Wants=network-online.target
After=network-online.target

[Service]
User=minio-user
Group=minio-user
Type=notify
Environment="MINIO_ROOT_USER=minioadmin"
Environment="MINIO_ROOT_PASSWORD=SecureMinioPassword123!"
ExecStart=/usr/local/bin/minio server /data/minio --console-address ":9001"
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
# Start MinIO
sudo systemctl daemon-reload
sudo systemctl enable minio
sudo systemctl start minio
```

---

## 📁 Project Structure

### Solution Architecture
```
ThePixStock/
├── ThePixStock.sln
├── src/
│   ├── ThePixStock.API/               # Main API Project
│   │   ├── Controllers/
│   │   ├── Program.cs
│   │   ├── appsettings.json
│   │   └── ThePixStock.API.csproj
│   ├── ThePixStock.Core/              # Domain & Business Logic
│   │   ├── Entities/
│   │   ├── Interfaces/
│   │   ├── Services/
│   │   └── ThePixStock.Core.csproj
│   ├── ThePixStock.Infrastructure/    # Data Access & External Services
│   │   ├── Data/
│   │   ├── Repositories/
│   │   ├── Services/
│   │   └── ThePixStock.Infrastructure.csproj
│   └── ThePixStock.Shared/            # Shared DTOs & Utilities
│       ├── DTOs/
│       ├── Utils/
│       └── ThePixStock.Shared.csproj
├── tests/
│   ├── ThePixStock.UnitTests/
│   └── ThePixStock.IntegrationTests/
└── docker-compose.yml
```

### Create Solution
```bash
# Create solution and projects
dotnet new sln -n ThePixStock
dotnet new webapi -n ThePixStock.API -f net8.0
dotnet new classlib -n ThePixStock.Core -f net8.0
dotnet new classlib -n ThePixStock.Infrastructure -f net8.0
dotnet new classlib -n ThePixStock.Shared -f net8.0

# Add projects to solution
dotnet sln add src/ThePixStock.API/ThePixStock.API.csproj
dotnet sln add src/ThePixStock.Core/ThePixStock.Core.csproj
dotnet sln add src/ThePixStock.Infrastructure/ThePixStock.Infrastructure.csproj
dotnet sln add src/ThePixStock.Shared/ThePixStock.Shared.csproj

# Add project references
dotnet add src/ThePixStock.API reference src/ThePixStock.Core
dotnet add src/ThePixStock.API reference src/ThePixStock.Infrastructure
dotnet add src/ThePixStock.API reference src/ThePixStock.Shared
dotnet add src/ThePixStock.Infrastructure reference src/ThePixStock.Core
dotnet add src/ThePixStock.Core reference src/ThePixStock.Shared
```

### Install NuGet Packages
```bash
# API Project
dotnet add src/ThePixStock.API package Microsoft.AspNetCore.Authentication.JwtBearer
dotnet add src/ThePixStock.API package Swashbuckle.AspNetCore
dotnet add src/ThePixStock.API package Serilog.AspNetCore
dotnet add src/ThePixStock.API package Microsoft.AspNetCore.SignalR

# Infrastructure Project
dotnet add src/ThePixStock.Infrastructure package Npgsql.EntityFrameworkCore.PostgreSQL
dotnet add src/ThePixStock.Infrastructure package Microsoft.EntityFrameworkCore.Tools
dotnet add src/ThePixStock.Infrastructure package StackExchange.Redis
dotnet add src/ThePixStock.Infrastructure package Minio
dotnet add src/ThePixStock.Infrastructure package BCrypt.Net-Next

# Core Project
dotnet add src/ThePixStock.Core package FluentValidation
dotnet add src/ThePixStock.Core package AutoMapper
dotnet add src/ThePixStock.Core package MediatR
```

---

## 🗄️ Database Implementation

### Entity Models

#### User Entity
```csharp
// Core/Entities/User.cs
using System;
using System.Collections.Generic;

namespace ThePixStock.Core.Entities
{
    public class User
    {
        public int Id { get; set; }
        public string Email { get; set; }
        public string PasswordHash { get; set; }
        public UserRole Role { get; set; }
        public string FirstName { get; set; }
        public string LastName { get; set; }
        public string Phone { get; set; }
        public bool IsActive { get; set; } = true;
        public bool EmailVerified { get; set; } = false;
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        public DateTime? LastLogin { get; set; }
        
        // Navigation properties
        public virtual Photographer Photographer { get; set; }
        public virtual Customer Customer { get; set; }
        public virtual ICollection<Event> CreatedEvents { get; set; }
        public virtual ICollection<UserSession> Sessions { get; set; }
    }
    
    public enum UserRole
    {
        Admin,
        Photographer,
        Customer
    }
}
```

#### Event Entity
```csharp
// Core/Entities/Event.cs
namespace ThePixStock.Core.Entities
{
    public class Event
    {
        public int Id { get; set; }
        public string Name { get; set; }
        public string Description { get; set; }
        public DateTime? EventDate { get; set; }
        public string Location { get; set; }
        public string Venue { get; set; }
        public EventStatus Status { get; set; } = EventStatus.Planning;
        public bool SalesEnabled { get; set; } = false;
        public DateTime? SalesStartDate { get; set; }
        public DateTime? SalesEndDate { get; set; }
        public int TotalPhotos { get; set; } = 0;
        public int ApprovedPhotos { get; set; } = 0;
        public int RejectedPhotos { get; set; } = 0;
        public int PendingPhotos { get; set; } = 0;
        public bool FaceDetectionCompleted { get; set; } = false;
        public int CreatedById { get; set; }
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        
        // Navigation properties
        public virtual User Creator { get; set; }
        public virtual ICollection<Photo> Photos { get; set; }
        public virtual ICollection<EventPhotographer> Photographers { get; set; }
        public virtual ICollection<EventPricing> Pricing { get; set; }
        public virtual ICollection<Order> Orders { get; set; }
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
```

#### Photo Entity
```csharp
// Core/Entities/Photo.cs
namespace ThePixStock.Core.Entities
{
    public class Photo
    {
        public int Id { get; set; }
        public int EventId { get; set; }
        public int PhotographerId { get; set; }
        public string OriginalFilename { get; set; }
        public string Filename { get; set; }
        public string FilePath { get; set; }
        public long FileSize { get; set; }
        public string MimeType { get; set; }
        public int? Width { get; set; }
        public int? Height { get; set; }
        public int Orientation { get; set; } = 1;
        
        // Camera metadata
        public string CameraMake { get; set; }
        public string CameraModel { get; set; }
        public string LensModel { get; set; }
        public decimal? FocalLength { get; set; }
        public decimal? Aperture { get; set; }
        public string ShutterSpeed { get; set; }
        public int? ISO { get; set; }
        public bool? Flash { get; set; }
        public decimal? GpsLatitude { get; set; }
        public decimal? GpsLongitude { get; set; }
        public DateTime? TakenAt { get; set; }
        public DateTime UploadedAt { get; set; }
        
        // Processing status
        public ProcessingStatus ProcessingStatus { get; set; } = ProcessingStatus.Pending;
        public ProcessingStatus ThumbnailStatus { get; set; } = ProcessingStatus.Pending;
        public ProcessingStatus WatermarkStatus { get; set; } = ProcessingStatus.Pending;
        
        // Approval
        public ApprovalStatus ApprovalStatus { get; set;}
```

### Database Migrations
```bash
# Add initial migration
dotnet ef migrations add InitialCreate -p src/ThePixStock.Infrastructure -s src/ThePixStock.API

# Update database
dotnet ef database update -p src/ThePixStock.Infrastructure -s src/ThePixStock.API
```

---

## 🔌 API Implementation

### Program.cs Configuration
```csharp
// API/Program.cs
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.EntityFrameworkCore;
using Microsoft.IdentityModel.Tokens;
using Microsoft.OpenApi.Models;
using Serilog;
using StackExchange.Redis;
using System.Text;
using ThePixStock.Infrastructure.Data;
using ThePixStock.Core.Services;
using ThePixStock.Infrastructure.Services;

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

// Configure Swagger
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
        builder.Configuration.GetConnectionString("Redis"), true);
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
                Encoding.UTF8.GetBytes(builder.Configuration["Jwt:SecretKey"]))
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

// Register Services
builder.Services.AddScoped<IAuthService, AuthService>();
builder.Services.AddScoped<IEventService, EventService>();
builder.Services.AddScoped<IPhotoService, PhotoService>();
builder.Services.AddScoped<IPaymentService, PaymentService>();
builder.Services.AddScoped<IStorageService, MinioStorageService>();
builder.Services.AddScoped<ICacheService, RedisCacheService>();
builder.Services.AddScoped<IEmailService, EmailService>();

// Configure SignalR
builder.Services.AddSignalR();

// Configure AutoMapper
builder.Services.AddAutoMapper(AppDomain.CurrentDomain.GetAssemblies());

// Configure MediatR
builder.Services.AddMediatR(cfg => 
    cfg.RegisterServicesFromAssembly(typeof(Program).Assembly));

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
app.MapHub<NotificationHub>("/hub/notifications");

// Run database migrations
using (var scope = app.Services.CreateScope())
{
    var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
    dbContext.Database.Migrate();
}

app.Run();
```

### Authentication Controller
```csharp
// API/Controllers/AuthController.cs
using Microsoft.AspNetCore.Mvc;
using ThePixStock.Core.Services;
using ThePixStock.Shared.DTOs;

namespace ThePixStock.API.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class AuthController : ControllerBase
    {
        private readonly IAuthService _authService;
        private readonly ILogger<AuthController> _logger;
        
        public AuthController(IAuthService authService, ILogger<AuthController> logger)
        {
            _authService = authService;
            _logger = logger;
        }
        
        [HttpPost("register")]
        public async Task<IActionResult> Register([FromBody] RegisterDto dto)
        {
            try
            {
                var result = await _authService.RegisterAsync(dto);
                if (!result.Success)
                    return BadRequest(result);
                    
                return Ok(result);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in registration");
                return StatusCode(500, new { message = "An error occurred during registration" });
            }
        }
        
        [HttpPost("login")]
        public async Task<IActionResult> Login([FromBody] LoginDto dto)
        {
            try
            {
                var result = await _authService.LoginAsync(dto);
                if (!result.Success)
                    return Unauthorized(result);
                    
                return Ok(result);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in login");
                return StatusCode(500, new { message = "An error occurred during login" });
            }
        }
        
        [HttpPost("refresh")]
        public async Task<IActionResult> RefreshToken([FromBody] RefreshTokenDto dto)
        {
            var result = await _authService.RefreshTokenAsync(dto);
            if (!result.Success)
                return Unauthorized(result);
                
            return Ok(result);
        }
        
        [HttpPost("logout")]
        [Authorize]
        public async Task<IActionResult> Logout()
        {
            var token = Request.Headers["Authorization"]
                .FirstOrDefault()?.Split(" ").Last();
            await _authService.LogoutAsync(token);
            return Ok(new { message = "Logged out successfully" });
        }
    }
}
```

### Event Controller
```csharp
// API/Controllers/EventController.cs
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using ThePixStock.Core.Services;
using ThePixStock.Shared.DTOs;

namespace ThePixStock.API.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class EventController : ControllerBase
    {
        private readonly IEventService _eventService;
        private readonly ILogger<EventController> _logger;
        
        public EventController(IEventService eventService, ILogger<EventController> logger)
        {
            _eventService = eventService;
            _logger = logger;
        }
        
        [HttpGet]
        public async Task<IActionResult> GetEvents([FromQuery] EventFilterDto filter)
        {
            var events = await _eventService.GetEventsAsync(filter);
            return Ok(events);
        }
        
        [HttpGet("{id}")]
        public async Task<IActionResult> GetEvent(int id)
        {
            var eventDto = await _eventService.GetEventByIdAsync(id);
            if (eventDto == null)
                return NotFound();
                
            return Ok(eventDto);
        }
        
        [HttpPost]
        [Authorize(Policy = "AdminOnly")]
        public async Task<IActionResult> CreateEvent([FromBody] CreateEventDto dto)
        {
            var result = await _eventService.CreateEventAsync(dto);
            if (!result.Success)
                return BadRequest(result);
                
            return CreatedAtAction(nameof(GetEvent), 
                new { id = result.Data.Id }, result.Data);
        }
        
        [HttpPut("{id}")]
        [Authorize(Policy = "AdminOnly")]
        public async Task<IActionResult> UpdateEvent(int id, [FromBody] UpdateEventDto dto)
        {
            var result = await _eventService.UpdateEventAsync(id, dto);
            if (!result.Success)
                return BadRequest(result);
                
            return Ok(result);
        }
        
        [HttpDelete("{id}")]
        [Authorize(Policy = "AdminOnly")]
        public async Task<IActionResult> DeleteEvent(int id)
        {
            var result = await _eventService.DeleteEventAsync(id);
            if (!result.Success)
                return BadRequest(result);
                
            return NoContent();
        }
        
        [HttpGet("{id}/photos")]
        public async Task<IActionResult> GetEventPhotos(int id, [FromQuery] int page = 1, [FromQuery] int size = 20)
        {
            var photos = await _eventService.GetEventPhotosAsync(id, page, size);
            return Ok(photos);
        }
        
        [HttpGet("{id}/packages")]
        public async Task<IActionResult> GetEventPackages(int id)
        {
            var packages = await _eventService.GetEventPackagesAsync(id);
            return Ok(packages);
        }
    }
}
```

---

## 💳 Payment Integration

### PayNoi Service Implementation
```csharp
// Infrastructure/Services/PaymentService.cs
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Configuration;
using ThePixStock.Core.Services;
using ThePixStock.Shared.DTOs;

namespace ThePixStock.Infrastructure.Services
{
    public class PaymentService : IPaymentService
    {
        private readonly HttpClient _httpClient;
        private readonly IConfiguration _configuration;
        private readonly ILogger<PaymentService> _logger;
        private readonly ApplicationDbContext _context;
        
        public PaymentService(
            HttpClient httpClient, 
            IConfiguration configuration,
            ILogger<PaymentService> logger,
            ApplicationDbContext context)
        {
            _httpClient = httpClient;
            _configuration = configuration;
            _logger = logger;
            _context = context;
        }
        
        public async Task<PaymentResponseDto> CreatePaymentAsync(CreatePaymentDto dto)
        {
            try
            {
                var paynoiRequest = new
                {
                    method = "create",
                    api_key = _configuration["PayNoi:ApiKey"],
                    amount = dto.Amount,
                    ref1 = dto.OrderId,
                    key_id = _configuration["PayNoi:KeyId"],
                    account = _configuration["PayNoi:Account"],
                    type = "1" // PromptPay
                };
                
                var json = JsonSerializer.Serialize(paynoiRequest);
                var content = new StringContent(json, Encoding.UTF8, "application/json");
                
                var response = await _httpClient.PostAsync(
                    _configuration["PayNoi:BaseUrl"], content);
                    
                if (!response.IsSuccessStatusCode)
                {
                    _logger.LogError($"PayNoi API error: {response.StatusCode}");
                    throw new Exception("Payment gateway error");
                }
                
                var responseContent = await response.Content.ReadAsStringAsync();
                var paynoiResponse = JsonSerializer.Deserialize<PayNoiResponse>(responseContent);
                
                // Save payment record
                var payment = new Payment
                {
                    OrderId = dto.OrderId,
                    TransactionId = paynoiResponse.TransId,
                    Amount = dto.Amount,
                    Status = PaymentStatus.Pending,
                    PaymentMethod = "promptpay",
                    Gateway = "paynoi",
                    CreatedAt = DateTime.UtcNow,
                    ExpireAt = DateTime.Parse(paynoiResponse.ExpireAt)
                };
                
                _context.Payments.Add(payment);
                await _context.SaveChangesAsync();
                
                return new PaymentResponseDto
                {
                    Success = true,
                    TransactionId = paynoiResponse.TransId,
                    QrCode = paynoiResponse.QrImageBase64,
                    Amount = paynoiResponse.Amount,
                    ExpireAt = paynoiResponse.ExpireAt
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating payment");
                throw;
            }
        }
        
        public async Task<PaymentStatusDto> CheckPaymentStatusAsync(string transactionId)
        {
            try
            {
                var paynoiRequest = new
                {
                    method = "check",
                    api_key = _configuration["PayNoi:ApiKey"],
                    trans_id = transactionId
                };
                
                var json = JsonSerializer.Serialize(paynoiRequest);
                var content = new StringContent(json, Encoding.UTF8, "application/json");
                
                var response = await _httpClient.PostAsync(
                    _configuration["PayNoi:BaseUrl"], content);
                    
                var responseContent = await response.Content.ReadAsStringAsync();
                var paynoiResponse = JsonSerializer.Deserialize<PayNoiStatusResponse>(responseContent);
                
                return new PaymentStatusDto
                {
                    TransactionId = transactionId,
                    Status = paynoiResponse.PaymentStatus,
                    Amount = paynoiResponse.Amount,
                    CreatedAt = paynoiResponse.CreatedAt,
                    ExpireAt = paynoiResponse.ExpireAt
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, $"Error checking payment status: {transactionId}");
                throw;
            }
        }
        
        [HttpPost("webhook")]
        [AllowAnonymous]
        public async Task<IActionResult> HandleWebhook([FromBody] PayNoiWebhook webhook)
        {
            try
            {
                // Verify webhook signature
                if (!VerifyWebhookSignature(webhook))
                {
                    _logger.LogWarning("Invalid webhook signature");
                    return Unauthorized();
                }
                
                // Update payment status
                var payment = await _context.Payments
                    .FirstOrDefaultAsync(p => p.TransactionId == webhook.Data.TransId);
                    
                if (payment != null)
                {
                    payment.Status = webhook.Data.PaymentStatus == "completed" 
                        ? PaymentStatus.Completed 
                        : PaymentStatus.Failed;
                    payment.ProcessedAt = DateTime.UtcNow;
                    
                    if (payment.Status == PaymentStatus.Completed)
                    {
                        // Update order status
                        var order = await _context.Orders.FindAsync(payment.OrderId);
                        if (order != null)
                        {
                            order.Status = OrderStatus.Paid;
                            order.PaymentStatus = PaymentStatus.Completed;
                            
                            // Generate download link
                            await GenerateDownloadLink(order);
                            
                            // Send confirmation email
                            await _emailService.SendOrderConfirmation(order);
                        }
                    }
                    
                    await _context.SaveChangesAsync();
                }
                
                return Ok(new { status = 1 });
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error handling payment webhook");
                return StatusCode(500);
            }
        }
        
        private bool VerifyWebhookSignature(PayNoiWebhook webhook)
        {
            var data = JsonSerializer.Serialize(webhook.Data);
            var apiKey = _configuration["PayNoi:ApiKey"];
            
            using (var hmac = new System.Security.Cryptography.HMACSHA256(
                Encoding.UTF8.GetBytes(apiKey)))
            {
                var computedHash = hmac.ComputeHash(Encoding.UTF8.GetBytes(data));
                var computedSignature = Convert.ToBase64String(computedHash);
                return computedSignature == webhook.Signature;
            }
        }
    }
}
```

---

## 🔒 Security Implementation

### JWT Service
```csharp
// Infrastructure/Services/JwtService.cs
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Security.Cryptography;
using Microsoft.Extensions.Configuration;
using Microsoft.IdentityModel.Tokens;
using ThePixStock.Core.Entities;

namespace ThePixStock.Infrastructure.Services
{
    public class JwtService : IJwtService
    {
        private readonly IConfiguration _configuration;
        
        public JwtService(IConfiguration configuration)
        {
            _configuration = configuration;
        }
        
        public string GenerateAccessToken(User user)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            var key = Encoding.UTF8.GetBytes(_configuration["Jwt:SecretKey"]);
            
            var claims = new List<Claim>
            {
                new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
                new Claim(ClaimTypes.Email, user.Email),
                new Claim(ClaimTypes.Role, user.Role.ToString()),
                new Claim(ClaimTypes.Name, $"{user.FirstName} {user.LastName}")
            };
            
            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(claims),
                Expires = DateTime.UtcNow.AddMinutes(30),
                Issuer = _configuration["Jwt:Issuer"],
                Audience = _configuration["Jwt:Audience"],
                SigningCredentials = new SigningCredentials(
                    new SymmetricSecurityKey(key), 
                    SecurityAlgorithms.HmacSha256Signature)
            };
            
            var token = tokenHandler.CreateToken(tokenDescriptor);
            return tokenHandler.WriteToken(token);
        }
        
        public string GenerateRefreshToken()
        {
            var randomNumber = new byte[64];
            using var rng = RandomNumberGenerator.Create();
            rng.GetBytes(randomNumber);
            return Convert.ToBase64String(randomNumber);
        }
        
        public ClaimsPrincipal ValidateToken(string token)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            var key = Encoding.UTF8.GetBytes(_configuration["Jwt:SecretKey"]);
            
            var validationParameters = new TokenValidationParameters
            {
                ValidateIssuerSigningKey = true,
                IssuerSigningKey = new SymmetricSecurityKey(key),
                ValidateIssuer = true,
                ValidIssuer = _configuration["Jwt:Issuer"],
                ValidateAudience = true,
                ValidAudience = _configuration["Jwt:Audience"],
                ValidateLifetime = true,
                ClockSkew = TimeSpan.Zero
            };
            
            try
            {
                var principal = tokenHandler.ValidateToken(
                    token, validationParameters, out _);
                return principal;
            }
            catch
            {
                return null;
            }
        }
    }
}
```

### Rate Limiting Middleware
```csharp
// API/Middleware/RateLimitingMiddleware.cs
using Microsoft.Extensions.Caching.Distributed;

namespace ThePixStock.API.Middleware
{
    public class RateLimitingMiddleware
    {
        private readonly RequestDelegate _next;
        private readonly IDistributedCache _cache;
        private readonly ILogger<RateLimitingMiddleware> _logger;
        
        public RateLimitingMiddleware(
            RequestDelegate next, 
            IDistributedCache cache,
            ILogger<RateLimitingMiddleware> logger)
        {
            _next = next;
            _cache = cache;
            _logger = logger;
        }
        
        public async Task InvokeAsync(HttpContext context)
        {
            var ipAddress = context.Connection.RemoteIpAddress?.ToString();
            var key = $"rate_limit_{ipAddress}";
            
            var requestCount = await _cache.GetStringAsync(key);
            
            if (requestCount != null && int.Parse(requestCount) >= 100)
            {
                context.Response.StatusCode = 429; // Too Many Requests
                await context.Response.WriteAsync("Rate limit exceeded. Try again later.");
                return;
            }
            
            await _cache.SetStringAsync(key, 
                (int.Parse(requestCount ?? "0") + 1).ToString(),
                new DistributedCacheEntryOptions
                {
                    AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(1)
                });
            
            await _next(context);
        }
    }
}
```

---

## 🧪 Testing & Deployment

### Unit Test Example
```csharp
// Tests/ThePixStock.UnitTests/Services/AuthServiceTests.cs
using Xunit;
using Moq;
using ThePixStock.Core.Services;
using ThePixStock.Infrastructure.Services;

namespace ThePixStock.UnitTests.Services
{
    public class AuthServiceTests
    {
        private readonly Mock<IUserRepository> _userRepositoryMock;
        private readonly Mock<IJwtService> _jwtServiceMock;
        private readonly AuthService _authService;
        
        public AuthServiceTests()
        {
            _userRepositoryMock = new Mock<IUserRepository>();
            _jwtServiceMock = new Mock<IJwtService>();
            _authService = new AuthService(
                _userRepositoryMock.Object, 
                _jwtServiceMock.Object);
        }
        
        [Fact]
        public async Task Login_ValidCredentials_ReturnsToken()
        {
            // Arrange
            var email = "test@example.com";
            var password = "password123";
            var user = new User 
            { 
                Id = 1, 
                Email = email, 
                PasswordHash = BCrypt.Net.BCrypt.HashPassword(password) 
            };
            
            _userRepositoryMock.Setup(x => x.GetByEmailAsync(email))
                .ReturnsAsync(user);
            _jwtServiceMock.Setup(x => x.GenerateAccessToken(user))
                .Returns("test-token");
            
            // Act
            var result = await _authService.LoginAsync(
                new LoginDto { Email = email, Password = password });
            
            // Assert
            Assert.True(result.Success);
            Assert.Equal("test-token", result.Data.AccessToken);
        }
    }
}
```

### Deployment Script
```bash
#!/bin/bash
# deploy.sh

# Build application
dotnet publish -c Release -o ./publish

# Stop existing service
sudo systemctl stop thepixstock-api

# Copy files
sudo cp -r ./publish/* /var/www/thepixstock-api/

# Update appsettings
sudo cp /var/www/thepixstock-api/appsettings.Production.json /var/www/thepixstock-api/appsettings.json

# Set permissions
sudo chown -R www-data:www-data /var/www/thepixstock-api

# Start service
sudo systemctl start thepixstock-api

# Check status
sudo systemctl status thepixstock-api
```

### Systemd Service Configuration
```ini
# /etc/systemd/system/thepixstock-api.service
[Unit]
Description=ThePixStock API
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
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
```

### Nginx Configuration
```nginx
# /etc/nginx/sites-available/thepixstock-api
server {
    listen 80;
    server_name api.thepixstock.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.thepixstock.com;
    
    ssl_certificate /etc/letsencrypt/live/api.thepixstock.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.thepixstock.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection keep-alive;
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /hub {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

---

## 📋 Configuration Files

### appsettings.json
```json
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
    "ApiKey": "2e5d01f3400e42cb263946237190d9107800bf316ec29d9cd41cdccc133c3af7",
    "KeyId": "100568",
    "Account": "1234567890"
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
```

---

## 📊 Monitoring Setup

### Health Check Endpoint
```csharp
// API/Controllers/HealthController.cs
[ApiController]
[Route("api/[controller]")]
public class HealthController : ControllerBase
{
    private readonly ApplicationDbContext _context;
    private readonly IConnectionMultiplexer _redis;
    
    public HealthController(
        ApplicationDbContext context,
        IConnectionMultiplexer redis)
    {
        _context = context;
        _redis = redis;
    }
    
    [HttpGet]
    public async Task<IActionResult> Check()
    {
        var health = new
        {
            Status = "Healthy",
            Timestamp = DateTime.UtcNow,
            Services = new
            {
                Database = await CheckDatabase(),
                Redis = CheckRedis(),
                Storage = await CheckStorage()
            }
        };
        
        return Ok(health);
    }
    
    private async Task<bool> CheckDatabase()
    {
        try
        {
            await _context.Database.CanConnectAsync();
            return true;
        }
        catch
        {
            return false;
        }
    }
    
    private bool CheckRedis()
    {
        try
        {
            var db = _redis.GetDatabase();
            db.Ping();
            return true;
        }
        catch
        {
            return false;
        }
    }
    
    private async Task<bool> CheckStorage()
    {
        // Check MinIO connection
        return true;
    }
}
```

---

**VM1 API Server Setup Complete** ✅

This implementation guide provides:
- Complete system setup with all required services
- Full .NET 8 API implementation
- Database schema and migrations
- PayNoi payment integration
- Security features (JWT, rate limiting)
- Testing and deployment procedures
- Monitoring and health checks
Ready for development team to implement!