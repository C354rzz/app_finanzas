from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class ConMarcasDeTiempo(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, password, **extra):
        if not email or not email.strip():
            raise ValueError("El email es obligatorio")
        usuario = self.model(email=email.strip().lower(), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._crear(email, password, **extra)

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email.strip())


class Usuario(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("email", unique=True)
    nombre = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField("acceso al admin", default=False)
    date_joined = models.DateTimeField("fecha de alta", default=timezone.now)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [models.UniqueConstraint(Lower("email"), name="usuario_email_unico_ci")]

    def __str__(self):
        return self.email


class Hogar(ConMarcasDeTiempo):
    nombre = models.CharField(max_length=120)
    moneda = models.CharField(max_length=3, default="MXN")
    zona_horaria = models.CharField(max_length=64, default="America/Monterrey")

    class Meta:
        verbose_name = "hogar"
        verbose_name_plural = "hogares"

    def __str__(self):
        return self.nombre


class Membresia(ConMarcasDeTiempo):
    class Rol(models.TextChoices):
        ADMIN = "admin", "Administrador"
        EDITOR = "editor", "Editor"
        LECTOR = "lector", "Lector"

    hogar = models.ForeignKey(Hogar, on_delete=models.CASCADE, related_name="membresias")
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="membresias")
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.ADMIN)

    class Meta:
        verbose_name = "membresía"
        verbose_name_plural = "membresías"
        constraints = [models.UniqueConstraint(fields=["hogar", "usuario"], name="membresia_unica")]

    def __str__(self):
        return f"{self.usuario} en {self.hogar} ({self.rol})"
