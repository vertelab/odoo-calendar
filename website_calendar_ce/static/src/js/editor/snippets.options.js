odoo.define('website_calendar_ce.form_editor_registry', function (require) {
'use strict';

var Registry = require('web.Registry');

return new Registry();

});

odoo.define('website_calendar_ce.list_project_form', function (require) {
'use strict';

    var core = require('web.core');
    var FormEditorRegistry = require('website_calendar_ce.form_editor_registry');

    var _t = core._t;

    FormEditorRegistry.add('select_project', {
        fields: [{
            name: 'bla',
            type: 'char',
            required: true,
            string: _t('T?'),
            defaultValue: 'kdnaksn@alksndkna',
        }],
    });
});


odoo.define('website_calendar_ce.s_testimonial_options', function (require) {
    'use strict';
    var options = require('web_editor.snippets.options');
    var rpc = require('web.rpc');




    options.registry.s_testimonial_options = options.Class.extend({
        _test_function: function() {
            console.log("andsnaskndkndnnnnN");
        },

        init: function() {
            const _super = this._super.bind(this);
            console.log("akndskansdk");
            return _super(...arguments);
        },

            /*rpc.query({
                model: 'calendar.booking.type',
                method: 'find_all_bookings',
            }).then(function (data) {
                var json_data = JSON.parse(data)
                for (let [key, value] of Object.entries(json_data)){
                    let row = document.createElement('we-button');
                    row.setAttribute("data-select-class", value["name"].replace(" ", "_"));
                    row.textContent = value["name"].replace(" ", "_");
                    booking_type_select.appendChild(row)
                    console.log(booking_type_select);
                }
            });
            console.log("actually done?");
            booking_type_select.addEventListener("change", this._test_function, false);*/
/*function modifyText() {
  const t2 = document.getElementById("t2");
  if (t2.firstChild.nodeValue == "three") {
    t2.firstChild.nodeValue = "two";
  } else {
    t2.firstChild.nodeValue = "three";
  }
}

// Add event listener to table
const el = document.getElementById("outside");
el.addEventListener("click", modifyText, false);*/

        willStart: async function () {
            const _super = this._super.bind(this);

            console.log("WILLSTART");
            var data = await this._rpc({
                model: 'calendar.booking.type',
                method: 'find_all_bookings',
            });
            this.projects = JSON.parse(data);
            this.active_project = this.projects[0].id;
            console.log(this.projects);

            this.selectProjectEl = document.createElement('we-select');
            this.selectProjectEl.setAttribute('string', 'Booking type');
            this.selectProjectEl.isSelect = 'true';
            this.selectProjectEl.dataset.noPreview = 'true';

            this.projects.forEach(project => {
                const option = document.createElement('we-button');
                option.textContent = project.name;
                option.dataset.selectAction = project.id;
                this.selectProjectEl.append(option);
            });
            console.log("Exit");
            return _super(...arguments);
        },

        onFocus: function() {
            console.log("kanskdnasndknaksnd");
        },

        selectAction: async function (previewMode, value, params) {
            await this._applyModel(parseInt(value));
            this.rerender = true;
        },

        _applyModel: async function (id) {
            console.log("applymodel for id " + id);

        },

        _renderCustomXML: function(uiFragment) {
            console.log("HELLO");
            // Add Action select
            const firstOption = uiFragment.childNodes[0];
            uiFragment.insertBefore(this.selectProjectEl.cloneNode(true), firstOption);
            return uiFragment;
        }
        /*start: function(a, b, c) {
            alert("HELLO!");
        },*/
        /*        onChange: function(e) {

            console.log("I CHANGED!");
            console.log(e);
        }*/


        /**
         * @override
         */
//        asdknaskndkn_renderCustomXML: function (uiFragment) {
/*            if (this.modelCantChange) {
                return;
            }*/
            // Add Action select
            //            const firstOption = uiFragment.childNodes[0];
            //uiFragment.insertBefore(this.selectProjectEl.cloneNode(true), firstOption);

            // Add Action related options
            //return;
            /*
            const formKey = this.activeForm.website_form_key;
            const formInfo = FormEditorRegistry.get(formKey);
            if (!formInfo || !formInfo.fields) {
                return;
            }
            const proms = formInfo.fields.map(field => this._fetchFieldRecords(field));
            return Promise.all(proms).then(() => {
                formInfo.fields.forEach(field => {
                    let option;
                    switch (field.type) {
                        case 'many2one':
                            option = this._buildSelect(field);
                            break;
                        case 'char':
                            option = this._buildInput(field);
                            break;
                    }
                    if (field.required) {
                        // Try to retrieve hidden value in form, else,
                        // get default value or for many2one fields the first option.
                        const currentValue = this.$target.find(`.s_website_form_dnone input[name="${field.name}"]`).val();
                        const defaultValue = field.defaultValue || field.records[0].id;
                        this._addHiddenField(currentValue || defaultValue, field.name);
                    }
                    uiFragment.insertBefore(option, firstOption);
                });
            });*/
  //      },


    });


})

