"""
Serializers for course API endpoints (React components).
"""
from rest_framework import serializers
from .models import Course, Workshop, Venue


class VenueSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='venue_name', read_only=True)
    city = serializers.CharField(source='location', read_only=True)

    class Meta:
        model = Venue
        fields = ['id', 'name', 'venue_name', 'slug', 'location', 'city', 'venue_address']


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'short_description', 'level', 'category',
            'duration_hours', 'price', 'what_youll_learn'
        ]


class WorkshopSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    venue = VenueSerializer(read_only=True)
    location = VenueSerializer(source='venue', read_only=True)  # compatibility
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    spaces_available = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)

    class Meta:
        model = Workshop
        fields = [
            'id', 'course', 'venue', 'location', 'start_date', 'end_date',
            'price', 'spaces_available', 'is_full', 'enrollment_open'
        ]
