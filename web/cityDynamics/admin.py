from django.contrib import admin
from cityDynamics.api.models import LengteGewicht
from leaflet.admin import LeafletGeoAdmin

# Change header name
admin.site.site_header = 'cityDynamics'

# Register your models here.



# //////////////////////////////////////////////
# Main Project
# /////////////////////////////////////////////


# class BeeldmaatlattenAdmin(LeafletGeoAdmin, admin.ModelAdmin):
#     list_projects = ('name')
#     #inlines = [WerkorderInline, ProjectPlanInline]


admin.site.register(LengteGewicht)


