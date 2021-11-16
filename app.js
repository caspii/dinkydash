console.log("Hello World")



const dinkyApp = {
    data() {
        return {
            message: "Hello world"
        }
    },
}
    
Vue.createApp(dinkyApp).mount('#app')