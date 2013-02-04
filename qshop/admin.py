from django.contrib import admin
from .models import Product, ProductVariationValue, ProductVariation, ProductImage, ParametersSet, Parameter, ProductToParameter, ParameterValue
#from django.db import models

from .admin_forms import ProductToParameterFormset, CategoryForm, PriceForm

from .admin_filters import ProductCategoryListFilter

from django.conf import settings

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.admin import helpers
from django.http import HttpResponseRedirect
from sitemenu import import_item
from sitemenu.sitemenu_settings import MENUCLASS
from decimal import Decimal

Menu = import_item(MENUCLASS)


class ProductVariationInline(admin.TabularInline):
    model = ProductVariation
    extra = 1


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductToParameterInline(admin.TabularInline):
    model = ProductToParameter
    #formset = ProductToTypeFieldFormset
    extra = 0
    can_delete = False
    #readonly_fields = ('parameter',)
    formset = ProductToParameterFormset
    fieldsets = (
        (None, {
            'fields': ('parameter', 'value'),
        }),
    )

    def has_add_permission(self, request):
        return False


class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductVariationInline, ProductImageInline, ProductToParameterInline]
    prepopulated_fields = {"articul": ("name",)}
    list_display = ('articul', 'name', 'has_variations', 'admin_price_display', 'sort')
    list_editable = ('sort',)
    list_filter = ('parameters_set', ProductCategoryListFilter)
    actions = ['link_to_category', 'unlink_from_category', 'change_price', 'set_discount']

    filter_horizontal = ('category',)

    def save_formset(self, request, form, formset, change):
        super(ProductAdmin, self).save_formset(request, form, formset, change)

        if formset.model == ProductToParameter:
            obj = formset.instance
            if obj.is_parametrs_set_changed():
                for current_ptp in ProductToParameter.objects.filter(product=obj):
                    current_ptp.delete()
                for parameter in obj.parameters_set.parameter_set.all():
                    ptp = ProductToParameter()
                    ptp.parameter = parameter
                    ptp.product = obj
                    ptp.save()

        if formset.model == ProductVariation:
            obj = formset.instance
            variations = obj.productvariation_set.all()
            price = None
            discount_price = None
            for variation in variations:
                if not price or variation.get_price() < price:
                    price = variation.get_price_real()
                    discount_price = variation.get_price_discount()

            obj.has_variations = bool(variations)
            if price:
                obj.price = price
                obj.discount_price = discount_price
            obj.save()

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.has_variations:
            readonly_fields = list(self.readonly_fields) + ['price', 'discount_price']
        else:
            readonly_fields = self.readonly_fields
        return readonly_fields

    class Media:
        js = (
            settings.STATIC_URL + 'admin/qshop/js/products.js',
            settings.STATIC_URL + 'admin/sitemenu/js/images.js',
        )
        css = {
            'screen': (settings.STATIC_URL + 'admin/qshop/css/products.css', settings.STATIC_URL + 'admin/sitemenu/css/images.css',),
        }

    def link_to_category(self, request, queryset):

        if 'apply' in request.POST:
            form = CategoryForm(request.POST)
            if form.is_valid():
                cat = form.cleaned_data.get('category')

                for obj in queryset:
                    obj.category.add(cat)

                self.message_user(request, "Successfully linked products to '%s'." % (cat))
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = CategoryForm()

        return render_to_response('qshop/admin/actions/link_to_category.html', {
            'form': form,
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }, context_instance=RequestContext(request))
    link_to_category.short_description = "Link to category"

    def unlink_from_category(self, request, queryset):
        cats = Menu.objects.filter(product__in=queryset).distinct()

        if 'apply' in request.POST:
            form = CategoryForm(request.POST, qs=cats)
            if form.is_valid():
                cat = form.cleaned_data.get('category')

                for obj in queryset:
                    obj.category.remove(cat)

                self.message_user(request, "Successfully unlinked products from '%s'." % (cat))
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = CategoryForm(qs=cats)

        return render_to_response('qshop/admin/actions/unlink_from_category.html', {
            'form': form,
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }, context_instance=RequestContext(request))
    unlink_from_category.short_description = "Unlink from category"

    def change_price(self, request, queryset):
        if 'apply' in request.POST:
            form = PriceForm(request.POST)
            if form.is_valid():
                percent = form.cleaned_data.get('percent')
                percent_multiplier = Decimal(percent / Decimal(100) + Decimal(1))
                for obj in queryset:
                    obj.price = obj.price * percent_multiplier
                    if obj.discount_price:
                        obj.discount_price = obj.discount_price * percent_multiplier
                    if obj.has_variations:
                        for variation in obj.get_variations():
                            variation.price = variation.price * percent_multiplier
                            if variation.discount_price:
                                variation.discount_price = variation.discount_price * percent_multiplier
                            variation.save()
                    obj.save()

                self.message_user(request, "Successfully changed prices.")
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = PriceForm()

        return render_to_response('qshop/admin/actions/change_price.html', {
            'form': form,
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }, context_instance=RequestContext(request))
    change_price.short_description = "Change price by percent"

    def set_discount(self, request, queryset):
        if 'apply' in request.POST:
            form = PriceForm(request.POST)
            if form.is_valid():
                percent = form.cleaned_data.get('percent')
                if percent == 0:
                    get_price = lambda x: None
                else:
                    get_price = lambda x: x * Decimal(-percent / Decimal(100) + Decimal(1))
                for obj in queryset:
                    obj.discount_price = get_price(obj.price)
                    if obj.has_variations:
                        for variation in obj.get_variations():
                            variation.discount_price = get_price(variation.price)
                            variation.save()
                    obj.save()

                self.message_user(request, "Successfully setted discounts.")
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = PriceForm()

        return render_to_response('qshop/admin/actions/set_discount.html', {
            'form': form,
            'queryset': queryset,
            'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
        }, context_instance=RequestContext(request))
    set_discount.short_description = "Set discount by percent"

admin.site.register(Product, ProductAdmin)


class ParameterInline(admin.TabularInline):
    model = Parameter


class ParametersSetAdmin(admin.ModelAdmin):
    inlines = [ParameterInline]


admin.site.register(ParametersSet, ParametersSetAdmin)


class ParameterValueAdmin(admin.ModelAdmin):
    list_display = ('value', 'parameter')

    class Media:
        js = (
            settings.STATIC_URL + 'admin/qshop/js/products_parametervalues.js',
        )

admin.site.register(ParameterValue, ParameterValueAdmin)


class ProductVariationValueAdmin(admin.ModelAdmin):
    list_display = ('value',)

admin.site.register(ProductVariationValue, ProductVariationValueAdmin)
