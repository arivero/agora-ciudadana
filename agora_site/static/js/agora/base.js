if (window.gettext === undefined) {
    window.gettext = function(text) {
        return text;
    };
}

if (window.escapeAttribute === undefined) {
    window.escapeAttribute = function(text) {
        if (!!text && text.replace) {
            return text.replace(/[^0-9a-zA-Z ]+/gi, '');
        } else {
            return text;
        }
    };
}

(function() {
    var Agora = this.Agora = {};
    var app = this.app = {};

    Agora.TopView = Backbone.View.extend({
        el: "#top-bar",

        events: {},

        initialize: function() {
            _.bindAll(this);
        }
    });

    Agora.MainView = Backbone.View.extend({
        el: "body",

        events: {
            "click a.action-form-link": "onActionFormLinkClicked"
        },

        initialize: function() {
            _.bindAll(this);

            $(document).ajaxStop(this.updateUi);

            this.updateUi();
            this.setMomentLang();

            this.topBar = new Agora.TopView();
        },

        updateUi: function() {
        },

        setMomentLang: function() {
            moment.lang(this.$el.data('lang'));
        },

        onActionFormLinkClicked: function(event) {
            event.preventDefault();
            var target = $(event.currentTarget);
            this.$("#post-action-form").attr('action', target.attr('href'));
            this.$("#post-action-form").submit();
        }
    });

    app.main = new Agora.MainView();

    /*
     * Top messages block.
    */

    Agora.MessagesBox = Backbone.View.extend({
        el: "#messages-box",

        initialize: function() {
            var modal = this.$(".modal");
            if (modal.length > 0) {
                this.$('.modal').modal('show');
            }
        }
    });

    app.messages = new Agora.MessagesBox();

    Agora.round2decimals = function(num) {
        return Math.round(num * 100) / 100;
    }
}).call(this);
