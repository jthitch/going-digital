"""
Serializers for course API endpoints (React components).
"""
from rest_framework import serializers
from .models import Course, CourseInstance, Location, Instructor


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'city', 'state', 'address_line_1', 'postal_code']


class InstructorSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = Instructor
        fields = ['id', 'name', 'bio', 'specialties', 'years_experience']
    
    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'short_description', 'level', 'category',
            'duration_hours', 'price', 'what_youll_learn'
        ]


class CourseInstanceSerializer(serializers.ModelSerializer):
    course = CourseSerializer(read_only=True)
    location = LocationSerializer(read_only=True)
    instructor = InstructorSerializer(read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    spaces_available = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = CourseInstance
        fields = [
            'id', 'course', 'location', 'instructor', 'start_date', 'end_date',
            'price', 'spaces_available', 'is_full', 'enrollment_open'
        ]
